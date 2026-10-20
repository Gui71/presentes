import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Importa SQLite de stdin SOMENTE se o banco de destino não existir. Não substitui dados."

    def handle(self,*args,**options):
        config=settings.DATABASES['default']
        if config['ENGINE']!='django.db.backends.sqlite3':raise CommandError('Backend incompatível.')
        path=Path(config['NAME'])
        if path.exists() or path.is_symlink():raise CommandError('Destino existente: use volumes novos e mantenha o backup anterior.')
        if not path.parent.is_dir():raise CommandError('Diretório do banco ausente.')
        descriptor,name=tempfile.mkstemp(prefix='.restore-',dir=path.parent)
        temporary=Path(name)
        try:
            with os.fdopen(descriptor,'wb') as stream:shutil.copyfileobj(sys.stdin.buffer,stream)
            with sqlite3.connect(temporary.as_uri()+'?mode=ro',uri=True) as database:
                if database.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise CommandError('Snapshot inválido.')
                if not database.execute("SELECT 1 FROM sqlite_master WHERE name='django_migrations'").fetchone():raise CommandError('O snapshot não contém as migrations do projeto.')
            # Link cria o destino de forma exclusiva; outra criação nunca é sobrescrita.
            os.link(temporary,path)
            self.stdout.write('Snapshot importado em destino vazio.')
        finally:temporary.unlink(missing_ok=True)
