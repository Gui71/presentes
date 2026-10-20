import logging

from django.db import transaction
from django.db.models import F
from PIL import Image

from .models import Product, ProductLink, Selection


class ProductConflict(ValueError):
    pass


def remove_unused_image(storage, name):
    if name and not Product.objects.filter(image=name).exists():
        try:
            storage.delete(name)
        except OSError:
            logging.getLogger(__name__).warning("Não foi possível remover uma foto antiga; verifique o armazenamento privado.")


def valid_stored_image(field):
    if not field:
        return False
    try:
        with field.storage.open(field.name, "rb") as stream:
            with Image.open(stream) as image:
                image.verify()
        return True
    except (OSError, ValueError):
        return False


def update_product(pk, revision, name, urls):
    with transaction.atomic():
        # A primeira escrita serializa edição, exclusão e confirmação inclusive no SQLite.
        if not Product.objects.filter(pk=pk, revision=revision).update(revision=F("revision") + 1):
            raise ProductConflict("O item mudou. Atualize o painel antes de editar.")
        product = Product.objects.get(pk=pk)
        if Selection.objects.filter(product=product).exists():
            raise ProductConflict("Cancele a escolha antes de editar este presente.")
        product.name = name
        ProductLink.objects.filter(product=product).delete()
        ProductLink.objects.bulk_create([
            ProductLink(product=product, url=url, position=index)
            for index, url in enumerate(urls)
        ])
        # Alterar nome/links não substitui uma imagem existente sem confirmação.
        product.save(update_fields=["name"])
        return product


def delete_product(pk, revision):
    with transaction.atomic():
        if not Product.objects.filter(pk=pk, revision=revision).update(revision=F("revision") + 1):
            if not Product.objects.filter(pk=pk).exists():
                return  # Reenvio da exclusão concluída: idempotente.
            raise ProductConflict("O item mudou. Confira os dados antes de excluir.")
        if Selection.objects.filter(product_id=pk).exists():
            raise ProductConflict("Cancele a escolha antes de excluir este presente.")
        Product.objects.get(pk=pk).delete()
