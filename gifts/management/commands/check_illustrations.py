from django.core.management.base import BaseCommand, CommandError

from gifts.illustrations import catalog, match_illustration, read_illustration


class Command(BaseCommand):
    help = "Valida os arquivos do catálogo e, com --name, a correspondência de um nome, sem alterar presentes."

    def add_arguments(self, parser):
        parser.add_argument("--name", help="Nome exato do presente para testar a correspondência no catálogo.")

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
        if options["name"] is not None:
            candidate = match_illustration(options["name"])
            if candidate is None:
                raise CommandError("Nome sem correspondência única no catálogo. Use um nome claro ou inclua o objeto no catálogo.")
            self.stdout.write(self.style.SUCCESS(f"Nome compatível: {candidate.label} ({candidate.key})."))
