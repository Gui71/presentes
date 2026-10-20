import http.client
import io
import socket
from unittest import TestCase
from unittest.mock import MagicMock, patch

from PIL import Image

from gifts.external import (
    Budget, FetchError, MAX_HTML, PinnedConnection, PinnedTLSConnection,
    fetch, image_candidates, obtain_product_image, recode_image,
    resolve_public, validate_public_url,
)
from gifts.stores import identify_store


def raster(color="red", size=(100, 100)):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, "PNG")
    return output.getvalue()


class ExternalTests(TestCase):
    def test_store_domain_boundaries_and_unknown_domains(self):
        self.assertEqual(identify_store("https://www.mercadolivre.com.br/produto")["style"], "mercado")
        self.assertEqual(identify_store("https://magazineluiza.com.br/p")["style"], "magalu")
        for url in ("https://mercadolivre.com.br.evil.example/p", "https://fakemagalu.com/p", "https://other.example/p"):
            self.assertFalse(identify_store(url)["known"])
            self.assertEqual(identify_store(url)["label"], "Ver na loja")

    def test_internal_literal_hosts_credentials_schemes_ports_and_controls_are_blocked(self):
        bad = ["http://localhost", "http://sub.localhost/x", "http://metadata.google.internal/", "http://service.local/",
               "http://127.0.0.1/", "http://10.0.0.1/", "http://169.254.169.254/", "http://0.0.0.0/", "http://224.0.0.1/",
               "http://[::1]/", "http://[fd00::1]/", "http://[fe80::1]/", "http://[::ffff:127.0.0.1]/",
               "http://[64:ff9b::7f00:1]/", "file:///etc/passwd", "ftp://public.example/file", "https://user:pass@public.example/",
               "https://public.example:444/", "http://public.example:443/", "https://public.example/\r\nHeader: injected", "http://evil.example\\@localhost/"]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(FetchError):
                validate_public_url(url)

    @patch("gifts.external.socket.getaddrinfo")
    def test_dns_rejects_private_and_mixed_address_sets(self, lookup):
        for values in (["10.0.0.1"], ["8.8.8.8", "127.0.0.1"], ["::1"]):
            lookup.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (value, 443)) for value in values]
            with self.assertRaises(FetchError):
                resolve_public("shop.example", 443, Budget())

    @patch("gifts.external.socket.create_connection")
    def test_connection_uses_validated_ip_and_checks_actual_peer(self, connect):
        connect.return_value.getpeername.return_value = ("8.8.8.8", 80)
        connection = PinnedConnection("shop.example", 80, "8.8.8.8", timeout=2)
        connection.connect()
        connect.assert_called_once_with(("8.8.8.8", 80), 2)
        connect.return_value.getpeername.return_value = ("127.0.0.1", 80)
        with self.assertRaises(FetchError):
            connection.connect()

    @patch("gifts.external.ssl.create_default_context")
    @patch("gifts.external.socket.create_connection")
    def test_tls_uses_default_trust_and_original_hostname(self, connect, context):
        connect.return_value.getpeername.return_value = ("8.8.8.8", 443)
        PinnedTLSConnection("shop.example", 443, "8.8.8.8", timeout=2).connect()
        context.assert_called_once_with()
        context.return_value.wrap_socket.assert_called_once_with(connect.return_value, server_hostname="shop.example")

    @patch("gifts.external.resolve_public", return_value="8.8.8.8")
    @patch("gifts.external.PinnedTLSConnection")
    def test_private_redirect_blocked_before_second_connection(self, cls, resolver):
        response = cls.return_value.getresponse.return_value
        response.status = 302
        response.getheader.side_effect = lambda name, default=None: "http://169.254.169.254/latest" if name == "Location" else default
        with self.assertRaises(FetchError):
            fetch("https://shop.example/product", Budget(), MAX_HTML)
        self.assertEqual(cls.call_count, 1)

    @patch("gifts.external.resolve_public", return_value="8.8.8.8")
    @patch("gifts.external.PinnedTLSConnection")
    def test_redirect_hostname_is_revalidated_against_dns(self, cls, resolver):
        response = cls.return_value.getresponse.return_value
        response.status = 302
        response.getheader.side_effect = lambda name, default=None: "https://other.example/product" if name == "Location" else default
        resolver.side_effect = ["8.8.8.8", FetchError("private DNS")]
        with self.assertRaises(FetchError):
            fetch("https://shop.example/product", Budget(), MAX_HTML)
        self.assertEqual(resolver.call_count, 2)
        self.assertEqual(cls.call_count, 1)

    @patch("gifts.external.resolve_public", return_value="8.8.8.8")
    @patch("gifts.external.PinnedTLSConnection")
    def test_fetch_byte_and_redirect_limits(self, cls, resolver):
        response = cls.return_value.getresponse.return_value
        response.status = 200
        response.getheader.side_effect = lambda name, default=None: "9999999" if name == "Content-Length" else default
        with self.assertRaises(FetchError):
            fetch("https://shop.example/p", Budget(), 100)
        response.getheader.side_effect = lambda name, default=None: "https://shop.example/again" if name == "Location" else default
        response.status = 302
        cls.reset_mock()
        with self.assertRaises(FetchError):
            fetch("https://shop.example/p", Budget(), 100)
        self.assertEqual(cls.call_count, 5)

    @patch("gifts.external.resolve_public", return_value="8.8.8.8")
    @patch("gifts.external.PinnedTLSConnection")
    def test_stream_size_limit_without_content_length(self, cls, resolver):
        response = cls.return_value.getresponse.return_value
        response.isclosed.return_value = False
        response.status = 200
        response.getheader.side_effect = lambda name, default=None: default
        response.read1.return_value = b"x" * 101
        with self.assertRaises(FetchError):
            fetch("https://shop.example/p", Budget(), 100)

    def test_deadline_is_enforced(self):
        with self.assertRaises(FetchError):
            Budget(seconds=-1).remaining()

    def test_metadata_does_not_select_unrelated_or_arbitrary_images(self):
        html = b'<title>Outra coisa</title><meta property="og:image" content="logo.png"><img src="advert.png">'
        self.assertEqual(image_candidates(html, "Cafeteira"), [])
        html = b'<title>Cafeteira</title><meta property="og:image" content="product.png"><img src="advert.png">'
        self.assertEqual(image_candidates(html, "Cafeteira"), ["product.png"])

    def test_jsonld_product_matching_and_malformed_metadata(self):
        html = b'<script type="application/ld+json">{"@graph":[{"@type":"Product","name":"Cafeteira","image":{"url":"photo.png"}},{"@type":"Organization","image":"logo.png"}]}</script>'
        self.assertEqual(image_candidates(html, "Cafeteira"), ["photo.png"])
        malformed = b'<script type="application/ld+json">{"@type":7}</script><script type="application/ld+json">broken</script>'
        self.assertEqual(image_candidates(malformed, "Cafeteira"), [])

    def test_raster_reencoded_and_invalid_svg_html_small_and_oversized_rejected(self):
        recoded = recode_image(raster())
        self.assertEqual(Image.open(io.BytesIO(recoded)).format, "WEBP")
        for body in (b"<svg></svg>", b"<html></html>", raster(size=(10, 10)), raster(size=(8001, 50))):
            with self.assertRaises((ValueError, OSError)):
                recode_image(body)

    @patch("gifts.external.fetch")
    def test_first_valid_photo_stops_following_links_and_resolves_relative_url(self, mocked):
        mocked.side_effect = [(b'<title>Cafeteira</title><meta property="og:image" content="../photo.png">', "text/html", "https://first.example/p/item"), (raster(), "image/png", "https://first.example/photo.png")]
        result = obtain_product_image(["https://first.example/p/item", "https://second.example/p"], "Cafeteira")
        self.assertTrue(result)
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(mocked.call_args_list[1].args[0], "https://first.example/photo.png")

    @patch("gifts.external.fetch")
    def test_failed_first_link_then_successful_second(self, mocked):
        mocked.side_effect = [FetchError("blocked store"), (b'<title>Cafeteira</title><meta property="og:image" content="/photo.png">', "text/html", "https://second.example/p"), (raster(), "image/png", "https://second.example/photo.png")]
        self.assertTrue(obtain_product_image(["https://first.example/p", "https://second.example/p"], "Cafeteira"))
        self.assertEqual(mocked.call_args_list[1].args[0], "https://second.example/p")

    @patch("gifts.external.fetch", side_effect=socket.timeout())
    def test_total_external_failure_returns_local_fallback(self, mocked):
        self.assertIsNone(obtain_product_image(["https://one.example/p", "https://two.example/p"], "Cafeteira"))

    @patch("gifts.external.fetch")
    def test_metadata_internal_image_url_is_not_trusted(self, mocked):
        # Exercita o fetch real da imagem, com metadado malicioso.
        real_fetch = fetch
        calls = []
        def route(url, budget, limit):
            calls.append(url)
            if len(calls) == 1:
                return b'<title>Cafeteira</title><meta property="og:image" content="http://127.0.0.1/secret">', "text/html", "https://shop.example/p"
            return real_fetch(url, budget, limit)
        mocked.side_effect = route
        self.assertIsNone(obtain_product_image(["https://shop.example/p"], "Cafeteira"))
        self.assertEqual(len(calls), 2)
