"""Snapshots consistentes de SQLite; nunca copiar o arquivo ativo."""
from pathlib import Path
from contextlib import closing
import sqlite3
import time


def sqlite_snapshot(source, target, timeout=20):
    source, target = Path(source).resolve(), Path(target).resolve()
    if not source.is_file() or source == target:
        raise ValueError("Banco de origem ausente ou destino inválido.")
    deadline = time.monotonic() + timeout

    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError("O snapshot excedeu o limite de tempo.")

    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=5)) as origin:
        with closing(sqlite3.connect(target, timeout=5)) as destination:
            origin.backup(destination, pages=256, progress=progress, sleep=0.05)
            if destination.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("O snapshot não passou pela verificação de integridade.")
