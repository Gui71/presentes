from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .external import validate_public_url


class VisitorForm(forms.Form):
    first_name = forms.CharField(label="Nome", max_length=60, widget=forms.TextInput(attrs={"autocomplete": "given-name", "autofocus": True}))
    surname = forms.CharField(label="Primeiro sobrenome", max_length=80, widget=forms.TextInput(attrs={"autocomplete": "family-name"}))


class ManagerAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.has_perm("gifts.view_product"):
            raise ValidationError("Sua conta não tem acesso ao painel. Consulte os anfitriões.", code="unauthorized")


class ProductForm(forms.Form):
    name = forms.CharField(label="Nome do produto", max_length=160, widget=forms.TextInput(attrs={"autofocus": True}))


class LinkForm(forms.Form):
    url = forms.URLField(label="Inserir link do anúncio", max_length=2048, widget=forms.URLInput(attrs={"placeholder": "https://…"}))

    def clean_url(self):
        url = self.cleaned_data["url"]
        # Validação sintática/IP literal aqui. DNS será validado e fixado no transporte.
        try:
            validate_public_url(url)
        except ValueError:
            raise ValidationError("Use um link HTTP ou HTTPS de uma loja pública, sem usuário ou senha.")
        return url


LinkFormSet = forms.formset_factory(LinkForm, extra=0, min_num=1, validate_min=True, max_num=10, validate_max=True, absolute_max=10)
