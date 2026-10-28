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

# Vocabulário fechado dos objetos do catálogo: não é um stemmer de português.
# Só estas flexões são equivalentes; palavras desconhecidas não são aproximadas.
_PLURALS = {
    "abridores": "abridor", "armarios": "armario", "aspiradores": "aspirador",
    "cabides": "cabide", "caixas": "caixa", "caixinhas": "caixinha", "cortadores": "cortador",
    "duplos": "duplo", "duplas": "dupla", "escovas": "escova", "escorredoras": "escorredora",
    "esteiras": "esteira", "fornos": "forno", "garrafas": "garrafa", "latas": "lata",
    "loucas": "louca", "luvas": "luva", "organizadores": "organizador", "organizadoras": "organizadora",
    "paredes": "parede", "raladores": "ralador", "rolhas": "rolha", "sanitarias": "sanitaria",
    "termicas": "termica", "vassouras": "vassoura", "xicaras": "xicara",
    "aparelhos": "aparelho", "acucareiros": "acucareiro", "aguas": "agua",
    "bacias": "bacia", "baldes": "balde", "banheiros": "banheiro",
    "batedeiras": "batedeira", "batedores": "batedor", "bocas": "boca",
    "bolos": "bolo", "cabos": "cabo", "cafeteiras": "cafeteira",
    "camas": "cama", "capas": "capa", "capsulas": "capsula",
    "cestos": "cesto", "chaleiras": "chaleira",
    "conjuntos": "conjunto", "copos": "copo", "cozinhas": "cozinha",
    "detergentes": "detergente", "eletricas": "eletrica", "eletricos": "eletrico",
    "escorredores": "escorredor", "facas": "faca", "faqueiros": "faqueiro",
    "ferros": "ferro", "filtros": "filtro", "formas": "forma",
    "frigideiras": "frigideira", "grandes": "grande", "hermeticos": "hermetico",
    "italianas": "italiana", "jarras": "jarra", "jogos": "jogo", "kits": "kit",
    "laminas": "lamina", "leiteiras": "leiteira", "lencois": "lencol",
    "lixeiras": "lixeira", "liquidificadores": "liquidificador",
    "macarroes": "macarrao", "mantimentos": "mantimento", "maquinas": "maquina",
    "mesas": "mesa", "miniprocessadores": "miniprocessador", "panelas": "panela",
    "panos": "pano", "pas": "pa", "pazinhas": "pazinha", "pecas": "peca",
    "pipoqueiras": "pipoqueira", "pirexes": "pirex", "piscinas": "piscina", "pizzas": "pizza",
    "placas": "placa", "plasticos": "plastico", "portas": "porta", "potes": "pote", "praias": "praia",
    "pratos": "prato", "prendedores": "prendedor", "processadores": "processador",
    "redondos": "redondo", "refratarios": "refratario", "retangulares": "retangular",
    "rodinhos": "rodinho", "rodos": "rodo", "roupas": "roupa", "sabonetes": "sabonete",
    "sacos": "saco", "saleiros": "saleiro", "sanduicheiras": "sanduicheira", "sobremesas": "sobremesa",
    "sucos": "suco", "suportes": "suporte", "tabuas": "tabua", "talheres": "talher",
    "tampas": "tampa", "tapetes": "tapete", "temperos": "tempero", "tesouras": "tesoura",
    "tigelas": "tigela", "toalhas": "toalha", "utensilios": "utensilio",
    "varais": "varal", "vidros": "vidro", "waffles": "waffle",
}
_PREPOSITIONS = frozenset({"de", "da", "do", "das", "dos", "para"})


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


def _matching_words(value):
    return tuple(_PLURALS.get(word, word) for word in normalize(value).split()
                 if word not in _PREPOSITIONS)


def _phrase_spans(words, phrase):
    size = len(phrase)
    if size:
        return [(start, start + size) for start in range(len(words) - size + 1)
                if words[start:start + size] == phrase]
    return []


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


def illustration_by_key(key):
    """Aceita somente uma chave exata do manifesto local, nunca um caminho."""
    return next((item for item in catalog() if item.key == key), None)


@lru_cache(maxsize=2048)
def match_illustration(name):
    """Correspondência explícita de nomes; nomes vagos/ambíguos ficam sem imagem."""
    words = _matching_words(name[:160])
    matches = []
    for item in catalog():
        spans = {span for alias in item.aliases for span in _phrase_spans(words, _matching_words(alias))}
        if spans:
            matches.append((item, spans))

    # "Panela de pipoca" contém "panela": a expressão específica ganha apenas
    # nesse trecho. "Panela de pipoca e panela" continua sendo dois objetos.
    candidates = [item for item, spans in matches
                  if any(not any(other_start <= start and end <= other_end
                                 and (other_start, other_end) != (start, end)
                                 for other, other_spans in matches if other.key != item.key
                                 for other_start, other_end in other_spans)
                         for start, end in spans)]
    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    if any(_phrase_spans(words, _matching_words(alias)) for alias in candidate.exclude):
        return None
    return candidate


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
