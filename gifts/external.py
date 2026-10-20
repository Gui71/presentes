"""HTTP público com DNS fixado na conexão, sem cookies, proxies ou JS remoto."""
import http.client
import io
import ipaddress
import json
import queue
import re
import socket
import ssl
import threading
import time
import unicodedata
import warnings
import codecs
import gzip
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

from PIL import Image, ImageOps

MAX_HTML = 1024 * 1024
MAX_IMAGE = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000
DNS_SLOTS = threading.BoundedSemaphore(4)


class FetchError(ValueError):
    pass


def public_ip(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise FetchError("Endereço inválido") from exc
    if (not address.is_global or address.is_multicast or address.is_reserved
            or address.is_loopback or address.is_link_local or address.is_unspecified
            or getattr(address, "ipv4_mapped", None) is not None
            or getattr(address, "is_site_local", False)):
        raise FetchError("Destino não público")
    if address.version == 6 and (
        address.sixtofour is not None or address.teredo is not None
        or address in ipaddress.ip_network("64:ff9b::/96")
        or address in ipaddress.ip_network("64:ff9b:1::/48")
    ):
        raise FetchError("Endereço de transição não permitido")
    return address


def validate_public_url(url):
    if len(url) > 2048 or any(char.isspace() or ord(char) < 32 for char in url) or "\\" in url:
        raise FetchError("URL inválida")
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or parsed.username is not None or parsed.password is not None:
            raise FetchError("Esquema ou credenciais não permitidos")
        host = (parsed.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except (ValueError, UnicodeError) as exc:
        raise FetchError("URL inválida") from exc
    if port != (443 if parsed.scheme == "https" else 80) or not host or len(host) > 253 or "%" in host:
        raise FetchError("Host ou porta não permitidos")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if ("." not in host or host.endswith((".localhost", ".local", ".internal", ".home", ".lan"))
                or not re.fullmatch(r"[a-z0-9.-]+", host)):
            raise FetchError("Host não público")
    else:
        public_ip(host)
    return parsed, host, port


@dataclass
class Budget:
    seconds: float = 12

    def __post_init__(self):
        self.deadline = time.monotonic() + self.seconds

    def remaining(self):
        value = self.deadline - time.monotonic()
        if value <= 0:
            raise FetchError("Limite de tempo atingido")
        return min(value, 3)


def resolve_public(host, port, budget):
    # Limita também DNS: getaddrinfo não oferece timeout portátil.
    if not DNS_SLOTS.acquire(blocking=False):
        raise FetchError("Resolução ocupada")
    result = queue.Queue(maxsize=1)

    def resolve():
        try:
            result.put(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
        except OSError as exc:
            result.put(exc)
        finally:
            DNS_SLOTS.release()

    threading.Thread(target=resolve, daemon=True).start()
    try:
        addresses = result.get(timeout=budget.remaining())
    except queue.Empty as exc:
        raise FetchError("DNS indisponível") from exc
    if isinstance(addresses, Exception):
        raise FetchError("DNS indisponível") from addresses
    if not addresses or len(addresses) > 32:
        raise FetchError("DNS inválido")
    validated = [public_ip(entry[4][0]) for entry in addresses]
    return str(validated[0])


class PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host, port, address, timeout):
        super().__init__(host, port, timeout=timeout)
        self.address = address
        self.budget = None

    def connect(self):
        # O hostname nunca é resolvido novamente por HTTPConnection.
        self.sock = socket.create_connection((self.address, self.port), self.budget.remaining() if self.budget else self.timeout)
        try:
            if public_ip(self.sock.getpeername()[0]) != public_ip(self.address):
                raise FetchError("Destino conectado inesperado")
        except Exception:
            self.sock.close()
            raise


class PinnedTLSConnection(PinnedConnection):
    def connect(self):
        super().connect()
        try:
            if self.budget:
                self.sock.settimeout(self.budget.remaining())
            self.sock = ssl.create_default_context().wrap_socket(self.sock, server_hostname=self.host)
        except Exception:
            self.sock.close()
            raise


def fetch(url, budget, limit):
    for redirect in range(5):
        parsed, host, port = validate_public_url(url)
        address = resolve_public(host, port, budget)
        cls = PinnedTLSConnection if parsed.scheme == "https" else PinnedConnection
        connection = cls(host, port, address, timeout=budget.remaining())
        connection.budget = budget
        response = None
        try:
            target = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
            if parsed.query:
                target += "?" + quote(parsed.query, safe="%=&/?+,:;@!$'()*-._~")
            connection.request("GET", target, headers={
                "User-Agent": "PresentesCasaNova/1.0", "Accept-Encoding": "identity",
                "Accept": "text/html,application/xhtml+xml,image/jpeg,image/png,image/webp",
            })
            transport = connection.sock
            transport.settimeout(budget.remaining())
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location or redirect == 4:
                    raise FetchError("Redirecionamentos inválidos")
                next_url = urljoin(url, location)
                if parsed.scheme == "https" and urlsplit(next_url).scheme == "http":
                    raise FetchError("Redirecionamento sem TLS")
                validate_public_url(next_url)
                url = next_url
                continue
            if response.status != 200:
                raise FetchError("Origem indisponível")
            encoding = response.getheader("Content-Encoding", "identity").lower()
            if encoding not in {"identity", "", "gzip"}:
                raise FetchError("Codificação não suportada")
            length = response.getheader("Content-Length")
            if length is not None and (not length.isdigit() or int(length) > limit):
                raise FetchError("Arquivo muito grande")
            chunks, size = [], 0
            while not response.isclosed():
                transport.settimeout(budget.remaining())
                chunk = response.read1(min(65536, limit + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > limit:
                    raise FetchError("Arquivo muito grande")
            body = b"".join(chunks)
            if encoding == "gzip":
                with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
                    body = compressed.read(limit + 1)
                if len(body) > limit:
                    raise FetchError("Conteúdo descomprimido muito grande")
            return body, response.getheader("Content-Type", "").split(";")[0].strip().lower(), url
        finally:
            if response is not None:
                response.close()
            connection.close()
    raise FetchError("Redirecionamentos demais")


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta, self.scripts, self.title = {}, [], ""
        self.primary_images = []
        self.in_title = self.in_json = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            self.meta.setdefault(key, attrs.get("content", ""))
        if tag == "img" and attrs.get("id") in {"landingImage", "imgBlkFront"}:
            self.primary_images.append((attrs.get("alt", ""), attrs.get("data-old-hires") or attrs.get("src", "")))
        self.in_title = self.in_title or tag == "title"
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self.in_json = True
            self.scripts.append("")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "script":
            self.in_json = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_json:
            self.scripts[-1] += data


def words(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return {word for word in re.findall(r"[a-z0-9]+", value) if len(word) > 2}


def image_candidates(html, product_name):
    parser = MetadataParser()
    charset = re.search(br'charset\s*=\s*["\x27]?\s*([a-zA-Z0-9_-]+)', html[:4096])
    encoding = "utf-8-sig"
    if charset:
        try:
            candidate = charset.group(1).decode("ascii")
            # Somente encodings de texto HTML usuais, nunca codecs executáveis/inadequados.
            if codecs.lookup(candidate).name in {"utf-8", "iso8859-1", "cp1252", "ascii"}:
                encoding = candidate
        except LookupError:
            pass
    parser.feed(html.decode(encoding, errors="replace"))
    expected = words(product_name)
    title_matches = bool(expected & words(parser.meta.get("og:title") or parser.meta.get("twitter:title") or parser.title))
    candidates = []
    if title_matches:
        candidates.extend(parser.meta.get(key, "") for key in ("og:image:secure_url", "og:image", "twitter:image", "twitter:image:src"))
    for alt, source in parser.primary_images:
        if expected & words(alt):
            candidates.append(source)

    def walk(value, depth=0):
        if depth > 12:
            return
        if isinstance(value, list):
            for item in value[:100]:
                walk(item, depth + 1)
        elif isinstance(value, dict):
            types = value.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if not isinstance(types, list):
                types = []
            is_product = any(isinstance(kind, str) and kind.rstrip("/").rsplit("/", 1)[-1] == "Product" for kind in types)
            if is_product and expected & words(str(value.get("name", ""))):
                images = value.get("image", [])
                if not isinstance(images, list):
                    images = [images]
                for image in images[:3]:
                    if isinstance(image, dict):
                        image = image.get("url") or image.get("contentUrl")
                    if isinstance(image, str):
                        candidates.append(image)
            for key in ("@graph", "mainEntity"):
                if key in value:
                    walk(value[key], depth + 1)

    for script in parser.scripts[:10]:
        try:
            walk(json.loads(script))
        except (ValueError, RecursionError):
            continue
    return list(dict.fromkeys(url for url in candidates if url))[:3]


def recode_image(body):
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(body)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"} or getattr(image, "is_animated", False):
                raise FetchError("Formato inválido")
            width, height = image.size
            if min(width, height) < 48 or max(width, height) > 8000 or width * height > MAX_PIXELS:
                raise FetchError("Dimensões inválidas")
            image.verify()
        with Image.open(io.BytesIO(body)) as original:
            image = ImageOps.exif_transpose(original).convert("RGBA")
            image.thumbnail((1000, 1000))
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.getchannel("A"))
            output = io.BytesIO()
            background.save(output, "WEBP", quality=82, method=4)
            return output.getvalue()


def obtain_product_image(urls, product_name):
    budget = Budget()
    for url in urls:
        try:
            html, mime, final_url = fetch(url, budget, MAX_HTML)
            if mime not in {"text/html", "application/xhtml+xml"}:
                continue
            for candidate in image_candidates(html, product_name):
                try:
                    body, image_mime, _ = fetch(urljoin(final_url, candidate), budget, MAX_IMAGE)
                    if image_mime not in {"image/jpeg", "image/png", "image/webp"}:
                        continue
                    return recode_image(body)
                except (ValueError, OSError, EOFError, http.client.HTTPException, Image.DecompressionBombWarning, Image.DecompressionBombError):
                    continue
        except (ValueError, OSError, EOFError, http.client.HTTPException, RecursionError):
            continue
    return None
