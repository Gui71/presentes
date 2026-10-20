from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def browser_session(sender, request, user, **kwargs):
    request.session.set_expiry(0)
