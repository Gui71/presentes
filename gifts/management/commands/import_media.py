import shutil
import sys
import tarfile
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help='Importa tar.gz de stdin em MEDIA_ROOT vazio, sem links ou caminhos externos.'
    def handle(self,*args,**options):
        root=Path(settings.MEDIA_ROOT)
        if root.is_symlink() or (root.exists() and any(root.iterdir())):raise CommandError('Mídia de destino deve estar vazia e não ser symlink.')
        root.mkdir(parents=True,exist_ok=True)
        with tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz') as archive:
            for member in archive:
                parts=Path(member.name).parts
                if not parts or parts[0]!='media' or '..' in parts or Path(member.name).is_absolute() or not (member.isfile() or member.isdir()):
                    raise CommandError('Arquivo de mídia inválido; destino parcial deve ser revisado antes de repetir.')
                target=root.joinpath(*parts[1:])
                if member.isdir():target.mkdir(parents=True,exist_ok=True,mode=0o700)
                else:
                    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                    with target.open('xb') as stream:shutil.copyfileobj(archive.extractfile(member),stream)
                    target.chmod(0o600)
        self.stdout.write('Mídia importada em destino vazio.')
