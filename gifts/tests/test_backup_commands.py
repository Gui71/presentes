import io
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from unittest import TestCase


class BackupCommandTests(TestCase):
    def test_snapshot_and_media_roundtrip_to_empty_destination_and_refusal_to_overwrite(self):
        project=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);media=root/'source-media';media.mkdir();(media/'fixture.webp').write_bytes(b'fixture')
            source=dict(os.environ,APP_ENV='test',SECRET_KEY=secrets.token_urlsafe(64),DATABASE_PATH=str(root/'source.sqlite3'),MEDIA_ROOT=str(media))
            target=dict(source,DATABASE_PATH=str(root/'target.sqlite3'),MEDIA_ROOT=str(root/'target-media'))
            def command(name,environment,data=None):
                return subprocess.run([sys.executable,'manage.py',name],cwd=project,env=environment,input=data,capture_output=True)
            result=command('migrate',source);self.assertEqual(result.returncode,0,result.stderr)
            database=command('backup_database',source);self.assertEqual(database.returncode,0,database.stderr)
            self.assertTrue(database.stdout.startswith(b'SQLite format 3'))
            result=command('import_snapshot',target,database.stdout);self.assertEqual(result.returncode,0,result.stderr)
            with sqlite3.connect(root/'target.sqlite3') as restored:self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone(),('ok',))
            before=(root/'target.sqlite3').read_bytes()
            self.assertNotEqual(command('import_snapshot',target,database.stdout).returncode,0)
            self.assertEqual((root/'target.sqlite3').read_bytes(),before)
            archive=command('backup_media',source);self.assertEqual(archive.returncode,0,archive.stderr)
            result=command('import_media',target,archive.stdout);self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual((root/'target-media/fixture.webp').read_bytes(),b'fixture')
            self.assertNotEqual(command('import_media',target,archive.stdout).returncode,0)
            malicious=io.BytesIO()
            with tarfile.open(fileobj=malicious,mode='w:gz') as tar:
                member=tarfile.TarInfo('media/../../outside');member.size=1;tar.addfile(member,io.BytesIO(b'x'))
            isolated=dict(target,MEDIA_ROOT=str(root/'clean-media'))
            self.assertNotEqual(command('import_media',isolated,malicious.getvalue()).returncode,0)
            self.assertFalse((root/'outside').exists())
