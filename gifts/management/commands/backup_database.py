import sys
from pathlib import Path
import shutil
import tempfile
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from gifts.backups import sqlite_snapshot


class Command(BaseCommand):
    help = "Escreve snapshot SQLite consistente em stdout; redirecione para arquivo privado."

    def handle(self, *args, **options):
        if sys.stdout.isatty():
            raise CommandError("Redirecione stdout para um arquivo privado .db.")
        if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('O backend precisa ser SQLite.')
        with tempfile.TemporaryDirectory(prefix='presentes-backup-') as directory:
            path=Path(directory)/'snapshot.db'
            path.touch(mode=0o600)
            sqlite_snapshot(settings.DATABASES['default']['NAME'],path)
            with path.open('rb') as stream:
                shutil.copyfileobj(stream,sys.stdout.buffer)
