"""Catálogo local de ilustrações; não faz chamadas a lojas ou APIs de geração."""
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import unicodedata

from PIL import Image


ROOT = Path(__file__).resolve().parent
MAX_ASSET_BYTES = 1024 * 1024


@dataclass(frozen=True)
class Illustration:
    key: str
    label: str
    aliases: tuple
    exclude: tuple
    digest: str

    @property
    def path(self):
        # Somente identificadores do manifesto versionado, nunca caminhos do navegador.
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", self.key):
            raise ValueError("Identificador de ilustração inválido.")
        return ROOT / "assets" / (self.key + ".webp")


def normalize(value):
    ascii_name = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", ascii_name))


@lru_cache(maxsize=1)
def catalog():
    with (ROOT / "catalog.json").open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    return tuple(Illustration(
        key=item["key"], label=item["label"],
        aliases=tuple(normalize(alias) for alias in item["aliases"]),
        exclude=tuple(normalize(alias) for alias in item.get("exclude", [])),
        digest=item["sha256"],
    ) for item in manifest["illustrations"])


@lru_cache(maxsize=2048)
def match_illustration(name):
    """Correspondência explícita de nomes; nomes vagos/ambíguos ficam sem imagem."""
    text = " " + normalize(name[:160]) + " "
    matches = [item for item in catalog()
               if any(" " + alias + " " in text for alias in item.aliases)
               and not any(" " + alias + " " in text for alias in item.exclude)]
    return matches[0] if len(matches) == 1 else None


def read_illustration(illustration):
    with illustration.path.open("rb") as stream:
        data = stream.read(MAX_ASSET_BYTES + 1)
    if len(data) > MAX_ASSET_BYTES or sha256(data).hexdigest() != illustration.digest:
        raise ValueError("Arquivo do catálogo ausente ou inválido.")
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "WEBP" or getattr(image, "is_animated", False):
            raise ValueError("Formato de ilustração inválido.")
        width, height = image.size
        if min(width, height) < 48 or max(width, height) > 1000:
            raise ValueError("Dimensões de ilustração inválidas.")
        image.verify()
    return data
