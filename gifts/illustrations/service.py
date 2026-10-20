from functools import partial
import uuid

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F

from gifts.models import Product
from gifts.services import ProductConflict, remove_unused_image, valid_stored_image
from . import match_illustration, read_illustration


def apply_illustration(pk, revision, replace_existing=False):
    """Aplica bytes locais validados; preserva a imagem até confirmar a substituição."""
    snapshot = Product.objects.filter(pk=pk).first()
    if snapshot is None:
        raise ProductConflict("O presente foi excluído. Atualize o painel.")
    candidate = match_illustration(snapshot.name)
    if candidate is None:
        return "no_match"
    # Leitura e validação de arquivo antes da transação, sem rede ou processamento de IA.
    data = read_illustration(candidate)
    created_file = None
    try:
        with transaction.atomic():
            if not Product.objects.filter(pk=pk, revision=revision).update(revision=F("revision") + 1):
                raise ProductConflict("O presente mudou. Confira o nome e a ilustração no painel antes de tentar novamente.")
            product = Product.objects.get(pk=pk)
            if product.name != snapshot.name:
                raise ProductConflict("O nome mudou durante a operação. Atualize o painel.")
            previous_valid = valid_stored_image(product.image)
            if previous_valid and not replace_existing:
                return "preserved"
            if (previous_valid and product.illustration_key == candidate.key
                    and product.illustration_digest == candidate.digest):
                return "unchanged"
            old_name, storage = product.image.name, product.image.storage
            new_name = storage.save(f"products/{uuid.uuid4().hex}.webp", ContentFile(data))
            created_file = (storage, new_name)
            product.image = new_name
            product.illustration_key = candidate.key
            product.illustration_digest = candidate.digest
            product.save(update_fields=["image", "illustration_key", "illustration_digest"])
            if old_name:
                transaction.on_commit(partial(remove_unused_image, storage, old_name))
        return "applied"
    except Exception:
        # Se o commit já ocorreu, nunca apagar o arquivo referenciado pelo banco.
        if created_file:
            remove_unused_image(*created_file)
        raise
