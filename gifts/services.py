from functools import partial
import logging

from django.db import transaction
from django.db.models import F
from django.core.files.base import ContentFile
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


def update_product(pk, revision, name, urls, photo, refresh_photo):
    new_file = None
    try:
        with transaction.atomic():
            # A primeira escrita serializa edição, exclusão e confirmação inclusive no SQLite.
            if not Product.objects.filter(pk=pk, revision=revision).update(revision=F("revision") + 1):
                raise ProductConflict("O item mudou. Atualize o painel antes de editar.")
            product = Product.objects.get(pk=pk)
            if Selection.objects.filter(product=product).exists():
                raise ProductConflict("Cancele a escolha antes de editar este presente.")
            old_name, storage = product.image.name, product.image.storage
            product.name = name
            ProductLink.objects.filter(product=product).delete()
            ProductLink.objects.bulk_create([ProductLink(product=product, url=url, position=index) for index, url in enumerate(urls)])
            if refresh_photo:
                if photo:
                    product.image.save("product.webp", ContentFile(photo), save=False)
                    new_file = (storage, product.image.name)
                elif not valid_stored_image(product.image):
                    product.image = ""
            product.save()
            if old_name and old_name != product.image.name:
                transaction.on_commit(partial(remove_unused_image, storage, old_name))
            return product
    except Exception:
        if new_file:
            new_file[0].delete(new_file[1])
        raise


def delete_product(pk, revision):
    with transaction.atomic():
        if not Product.objects.filter(pk=pk, revision=revision).update(revision=F("revision") + 1):
            if not Product.objects.filter(pk=pk).exists():
                return  # Reenvio da exclusão concluída: idempotente.
            raise ProductConflict("O item mudou. Confira os dados antes de excluir.")
        if Selection.objects.filter(product_id=pk).exists():
            raise ProductConflict("Cancele a escolha antes de excluir este presente.")
        Product.objects.get(pk=pk).delete()
