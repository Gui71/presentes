from django.core.management.base import BaseCommand, CommandError

from gifts.illustrations import catalog, read_illustration


class Command(BaseCommand):
    help = "Valida manifesto, integridade e raster do catálogo local, sem alterar presentes."

    def handle(self, *args, **options):
        try:
            items = catalog()
            if not items or len({item.key for item in items}) != len(items):
                raise ValueError("Catálogo vazio ou identificadores duplicados.")
            for item in items:
                if not item.aliases or not item.label:
                    raise ValueError("Ilustração sem nome ou correspondências.")
                read_illustration(item)
        except (OSError, ValueError, KeyError) as exc:
            raise CommandError("Catálogo inválido. Confira o manifesto e os arquivos versionados.") from exc
        self.stdout.write(self.style.SUCCESS(f"{len(items)} ilustrações locais válidas. Nenhum presente foi alterado."))
