import uuid
from django.conf import settings
from django.db import models


def product_image_path(instance, filename):
    return f"products/{uuid.uuid4().hex}.webp"


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("Nome do produto", max_length=160)
    image = models.ImageField("Foto automática", upload_to=product_image_path, blank=True)
    illustration_key = models.CharField(max_length=48, blank=True, editable=False)
    illustration_digest = models.CharField(max_length=64, blank=True, editable=False)
    illustration_choice = models.CharField(max_length=48, blank=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Cadastrado por")
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    submission_key = models.UUIDField(unique=True, editable=False)
    revision = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["-created_at", "id"]
        verbose_name = "presente"
        verbose_name_plural = "presentes"
        permissions = [
            ("export_database", "Pode baixar snapshot do banco"),
            ("export_selections", "Pode baixar planilha de conferência"),
        ]

    def __str__(self):
        return self.name

    @property
    def has_available_image(self):
        try:
            return bool(self.image and self.image.storage.exists(self.image.name))
        except OSError:
            return False

    @property
    def catalog_illustration(self):
        from .illustrations import illustration_by_key, match_illustration
        if self.illustration_choice:
            return illustration_by_key(self.illustration_choice)
        return match_illustration(self.name)

    @property
    def image_notice(self):
        candidate = self.catalog_illustration
        if self.has_available_image:
            if not self.illustration_key:
                return "Imagem existente preservada."
            if not candidate or candidate.key != self.illustration_key:
                return "O nome mudou. Confira se a ilustração ainda representa este presente."
            if self.illustration_choice:
                return "Ilustração escolhida no catálogo."
            return "Ilustração do catálogo aplicada."
        if candidate:
            return "Ilustração disponível no catálogo."
        return "Sem ilustração compatível pelo nome. Use Escolher ilustração para selecionar no catálogo."


class ProductLink(models.Model):
    product = models.ForeignKey(Product, related_name="links", on_delete=models.CASCADE)
    url = models.URLField("Link do anúncio", max_length=2048)
    position = models.PositiveSmallIntegerField("Ordem")

    class Meta:
        ordering = ["position", "pk"]
        constraints = [models.UniqueConstraint(fields=["product", "position"], name="unique_product_link_position")]
        verbose_name = "link de anúncio"
        verbose_name_plural = "links de anúncio"

    @property
    def store(self):
        from .stores import identify_store
        return identify_store(self.url)


class Selection(models.Model):
    product = models.OneToOneField(Product, related_name="selection", on_delete=models.PROTECT, verbose_name="Presente")
    owner_digest = models.CharField(max_length=64, editable=False)
    first_name = models.CharField("Nome", max_length=60)
    surname = models.CharField("Primeiro sobrenome", max_length=80)
    created_at = models.DateTimeField("Confirmado em", auto_now_add=True)

    @property
    def public_name(self):
        """Nome para o card público, sem modificar o sobrenome armazenado."""
        surname_words = self.surname.split()
        return " ".join(part for part in (self.first_name, surname_words[0] if surname_words else "") if part)

    class Meta:
        verbose_name = "escolha"
        verbose_name_plural = "escolhas"
        ordering = ["-created_at"]

    def __str__(self):
        return str(self.product)
