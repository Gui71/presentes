import sys
import tarfile
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help='Escreve mídia em tar.gz em stdout; redirecione para arquivo privado.'
    def handle(self,*args,**options):
        if sys.stdout.isatty():raise CommandError('Redirecione stdout para arquivo privado.')
        root=Path(settings.MEDIA_ROOT)
        with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
            if root.exists():archive.add(root,arcname='media',recursive=True)
