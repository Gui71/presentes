"""Flexões e expressões reais dos objetos ilustrados, sem NLP ou rede."""
import unicodedata

from django.test import SimpleTestCase

from gifts.illustrations import catalog, illustration_by_key, match_illustration, normalize


class IllustrationMatchingTests(SimpleTestCase):
    # Um exemplo singular e um plural de cada objeto do catálogo. Os conjuntos
    # são ilustrações genéricas: quantidade, marca e modelo vêm do anúncio.
    objects = {
        "cutlery": ("talher", "talheres"),
        "towel_set": ("toalha", "toalhas"),
        "dinnerware_set": ("prato", "pratos"),
        "drinking_glasses": ("copo", "copos"),
        "electric_kettle": ("chaleira elétrica", "chaleiras elétricas"),
        "blender": ("liquidificador", "liquidificadores"),
        "cookware_black": ("panela", "panelas"),
        "frying_pan": ("frigideira", "frigideiras"),
        "milk_pan": ("leiteira", "leiteiras"),
        "popcorn_pan": ("panela de pipoca", "pipoqueiras"),
        "kitchen_utensils": ("utensílio de cozinha", "utensílios de cozinhas"),
        "knife_set": ("faca", "facas"),
        "round_casserole": ("pirex redondo", "refratários redondos"),
        "rectangular_casserole": ("pirex retangular", "refratários retangulares"),
        "cake_pan": ("forma de bolo", "formas de bolo"),
        "pizza_pan": ("forma de pizza", "formas de pizza"),
        "salt_cellar": ("saleiro", "saleiros"),
        "sugar_bowl": ("açucareiro", "açucareiros"),
        "cutting_board": ("tábua de carne", "tábuas de corte"),
        "floor_cloths": ("pano de chão", "panos de chão"),
        "dish_towels": ("pano de prato", "panos de prato"),
        "clothespins": ("prendedor de roupa", "prendedores de roupas"),
        "buckets": ("balde", "baldes"),
        "dustpan": ("pá de lixo", "pás de lixo"),
        "sink_squeegee": ("rodinho de pia", "rodinhos de pia"),
        "laundry_basket": ("cesto de roupa", "cestos de roupas"),
        "wash_basins": ("bacia", "bacias"),
        "plastic_containers": ("pote de plástico", "potes plásticos"),
        "pantry_containers": ("pote hermético", "potes herméticos"),
        "glass_containers": ("pote de vidro", "potes de vidro"),
        "popcorn_bowl": ("pote para pipoca", "potes para pipoca"),
        "detergent_holder": ("porta detergente", "porta detergentes"),
        "pitcher": ("jarra", "jarras"),
        "kitchen_scissors": ("tesoura de cozinha", "tesouras de cozinha"),
        "colander": ("escorredor de macarrão", "escorredores de macarrão"),
        "spice_rack": ("porta tempero", "porta temperos"),
        "dessert_bowls": ("pote de sobremesa", "potes de sobremesa"),
        "soap_dish": ("porta sabonete", "porta sabonetes"),
        "waste_bin": ("lixeira", "lixeiras"),
        "bedding_set": ("roupa de cama", "jogos de roupas de cama"),
        "bath_mats": ("tapete de banheiro", "tapetes de banheiro"),
        "stand_mixer": ("batedeira", "batedeiras"),
        "coffee_maker": ("cafeteira", "cafeteiras"),
        "mini_processor": ("mini processador", "miniprocessadores"),
        "sandwich_maker": ("sanduicheira", "sanduicheiras"),
        "clothes_iron": ("ferro de passar", "ferros de passar"),
        "waffle_maker": ("mini máquina de waffle", "mini máquinas de waffles"),
    }

    def assert_matches(self, name, expected):
        candidate = match_illustration(name)
        self.assertIsNotNone(candidate, name)
        self.assertEqual(candidate.key, expected, name)

    def test_every_catalog_object_accepts_singular_plural_case_accents_and_punctuation(self):
        self.assertEqual(set(self.objects), {item.key for item in catalog()})
        for key, names in self.objects.items():
            for name in names:
                variants = {
                    name, name.upper(), name.title(), normalize(name),
                    "".join(letter.upper() if index % 2 else letter.lower() for index, letter in enumerate(name)),
                    unicodedata.normalize("NFD", name), " / ".join(name.split()),
                    f"* 2 - {name}!", "  ".join(name.split()),
                }
                for variant in variants:
                    with self.subTest(key=key, name=variant):
                        self.assert_matches(variant, key)

    def test_set_prefixes_and_controlled_prepositions_accept_the_requested_names(self):
        cases = {
            "Kit Panelas - pretas - Tramontina": "cookware_black",
            "JOGOS DE PANELAS": "cookware_black", "kit da panela": "cookware_black",
            "jogo de talher": "cutlery", "Conjuntos dos talheres": "cutlery",
            "Kit utensílios de cozinhas (colheres e etc)": "kitchen_utensils",
            "Frigideira com tampa": "frying_pan", "Cafeteira com filtro": "coffee_maker",
            "Pirex Redondo com tampa": "round_casserole",
            "5 panos de chão": "floor_cloths", "4 panos de prato": "dish_towels",
            "Kit potes herméticos para macarrão/arroz/etc": "pantry_containers",
            "Kit potes de vidro (borossilicato)": "glass_containers",
            "Pote grande para pipoca (plástico)": "popcorn_bowl",
            "Jarras para água (vidro)": "pitcher", "Jarra de suco (vidro ou plástico)": "pitcher",
            "Jogo Roupa de cama": "bedding_set", "jogos de lençóis": "bedding_set",
            "Kit Toalha": "towel_set", "Kit tapetes banheiro": "bath_mats",
            "Mini máquina de waffle pequena": "waffle_maker",
        }
        for name, key in cases.items():
            with self.subTest(name=name):
                self.assert_matches(name, key)

    def test_specific_object_wins_only_inside_its_own_expression(self):
        for name in ("panela de pipoca", "panela para pipoca", "panelas de pipoca",
                     "kit de panelas de pipoca", "Panela de pipoca (pipoqueira) - Tramontina"):
            with self.subTest(name=name):
                self.assert_matches(name, "popcorn_pan")
        for name in ("kit panela e liquidificador", "panelas e liquidificadores",
                     "panela de pipoca e panela", "pipoqueira e panelas",
                     "panela e chaleira elétrica", "panela e cafeteira italiana",
                     "jogo de talher e toalhas", "panos de prato e pratos"):
            with self.subTest(name=name):
                self.assertIsNone(match_illustration(name))

    def test_unknown_words_accessories_and_uncovered_variants_keep_the_fallback(self):
        names = (
            "Presente", "Produto", "kit", "B07WGQ64QR", "superpanela", "panelagem", "copoide",
            "Chaleira", "panela de pressão", "panelas de pressao", "panela elétrica",
            "panela de arroz", "panela a vapor", "panela de pipoca elétrica", "pipoqueiras elétricas",
            "cafeteiras italianas", "cápsulas para cafeteiras", "processador de alimentos",
            "toalhas de mesa", "toalhas de praia", "toalhas de papel", "toalha de cozinha",
            "porta-talheres", "suporte para talher", "porta pratos", "escorredores de pratos",
            "porta-copos", "copos para liquidificadores", "jarras para liquidificadores",
            "tampas de panelas", "cabos para panelas", "tampa de leiteira", "tampa de pipoqueira",
            "suporte para utensílios de cozinha", "afiador de facas", "porta-facas", "faca elétrica",
            "tampas para pirex redondos", "tampa de pote de vidro", "tampa de pote plástico",
            "sacos de lixeira", "suporte para toalhas", "tampas para mini processadores",
            "placas de sanduicheiras", "capa de ferro de passar", "placa de máquina de waffles",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertIsNone(match_illustration(name))

    def test_key_lookup_is_exact_and_cannot_be_used_as_a_path(self):
        for item in catalog():
            self.assertEqual(illustration_by_key(item.key), item)
        for key in (None, "", "unknown", "CUTLERY", "../cutlery", "cutlery.webp", "/etc/passwd"):
            with self.subTest(key=key):
                self.assertIsNone(illustration_by_key(key))
