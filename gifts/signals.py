from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.db.models.signals import post_delete
from django.db import transaction
from functools import partial
from .models import Product


@receiver(user_logged_in)
def browser_session(sender, request, user, **kwargs):
    request.session.set_expiry(0)


@receiver(post_delete, sender=Product)
def cleanup_product_image(sender, instance, **kwargs):
    from .services import remove_unused_image
    if instance.image:
        transaction.on_commit(partial(remove_unused_image, instance.image.storage, instance.image.name))
