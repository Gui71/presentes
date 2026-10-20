from urllib.parse import urlsplit

STORES = (
    (("mercadolivre.com.br", "mercadolivre.com", "mercadolibre.com", "meli.la"), "Mercado Livre", "mercado"),
    (("magazineluiza.com.br", "magalu.com", "magalu.com.br"), "Magalu", "magalu"),
    (("amazon.com.br", "amazon.com", "amzn.to"), "Amazon", "amazon"),
    (("casasbahia.com.br",), "Casas Bahia", "bahia"),
    (("shopee.com.br", "shope.ee"), "Shopee", "shopee"),
)


def identify_store(url):
    hostname = (urlsplit(url).hostname or "").lower().rstrip(".")
    for domains, label, style in STORES:
        if any(hostname == domain or hostname.endswith("." + domain) for domain in domains):
            prefix = "no" if label == "Mercado Livre" else "nas" if label == "Casas Bahia" else "na"
            return {"label": f"Ver {prefix} {label}", "style": style, "domain": hostname, "known": True}
    return {"label": "Ver na loja", "style": "neutral", "domain": hostname, "known": False}
