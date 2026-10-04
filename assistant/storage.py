"""Encrypted payloads, scoped queries, no transcript log or persistent audio."""
import json
import os
import sqlite3
import threading
import uuid
from pathlib import Path
from datetime import datetime, timezone
from cryptography.fernet import Fernet


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


class Store:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        key = directory / 'storage.key'
        if not key.exists():
            fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as f:
                f.write(Fernet.generate_key())
        self.cipher = Fernet(key.read_bytes())
        self.lock = threading.RLock()
        self.db = sqlite3.connect(directory / 'assistant.sqlite', check_same_thread=False)
        self.db.execute('PRAGMA secure_delete=ON')
        self.db.execute('CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY, kind TEXT, owner TEXT, payload BLOB)')
        self.db.commit()
        os.chmod(directory / 'assistant.sqlite', 0o600)

    def list(self, kind, owner):
        with self.lock:
            rows = self.db.execute('SELECT payload FROM entities WHERE kind=? AND owner=?', (kind, owner)).fetchall()
            return [json.loads(self.cipher.decrypt(r[0])) for r in rows]

    def put(self, kind, owner, data):
        data = dict(data)
        data.setdefault('id', uid())
        data.setdefault('created_at', now())
        with self.lock:
            existing = self.db.execute('SELECT kind,owner FROM entities WHERE id=?', (data['id'],)).fetchone()
            if existing and existing != (kind, owner):
                raise ValueError('Identificador fuera del ámbito autorizado')
            payload = self.cipher.encrypt(json.dumps(data, ensure_ascii=False).encode())
            self.db.execute('INSERT OR REPLACE INTO entities VALUES(?,?,?,?)', (data['id'], kind, owner, payload))
            self.db.commit()
        return data

    def get(self, kind, owner, entity_id):
        return next((x for x in self.list(kind, owner) if x['id'] == entity_id), None)

    def delete(self, kind, owner, entity_id):
        with self.lock:
            self.db.execute('DELETE FROM entities WHERE id=? AND kind=? AND owner=?', (entity_id, kind, owner))
            self.db.commit()
            self.db.execute('VACUUM')

    def close(self):
        self.db.close()
