from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class StoredObject:
    provider: str
    key: str
    url: str


class StorageBackend:
    provider: str

    def save_bytes(self, data: bytes, filename: str | None = None) -> StoredObject:
        raise NotImplementedError

    def save_file(self, file_obj: BinaryIO, filename: str | None = None) -> StoredObject:
        raise NotImplementedError

    def get_url(self, key: str) -> str:
        raise NotImplementedError


def resolve_local_storage_dir() -> Path:
    base_dir = Path(settings.LOCAL_STORAGE_DIR)
    if not base_dir.is_absolute():
        base_dir = _PROJECT_ROOT / base_dir
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def resolve_local_parsed_dir() -> Path:
    base_dir = Path(settings.LOCAL_PARSED_DIR)
    if not base_dir.is_absolute():
        base_dir = _PROJECT_ROOT / base_dir
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


class LocalStorageBackend(StorageBackend):
    provider = "local"

    def __init__(self, base_dir: Path, base_url: str):
        self.base_dir = base_dir
        self.base_url = base_url.rstrip("/")

    def _build_key(self, filename: str | None) -> str:
        suffix = ""
        if filename:
            suffix = Path(filename).suffix
        return f"{uuid.uuid4().hex}{suffix}"

    def save_bytes(self, data: bytes, filename: str | None = None) -> StoredObject:
        key = self._build_key(filename)
        path = self.base_dir / key
        path.write_bytes(data)
        return StoredObject(provider=self.provider, key=key, url=self.get_url(key))

    def save_file(self, file_obj: BinaryIO, filename: str | None = None) -> StoredObject:
        key = self._build_key(filename)
        path = self.base_dir / key
        with path.open("wb") as handle:
            shutil.copyfileobj(file_obj, handle)
        return StoredObject(provider=self.provider, key=key, url=self.get_url(key))

    def get_url(self, key: str) -> str:
        return f"{self.base_url}/{key}"


class OSSStorageBackend(StorageBackend):
    provider = "oss"

    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str, public_base_url: str):
        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.public_base_url = public_base_url.rstrip("/")

    def save_bytes(self, data: bytes, filename: str | None = None) -> StoredObject:
        raise RuntimeError("OSS backend is not implemented yet. Configure a client before enabling it.")

    def save_file(self, file_obj: BinaryIO, filename: str | None = None) -> StoredObject:
        raise RuntimeError("OSS backend is not implemented yet. Configure a client before enabling it.")

    def get_url(self, key: str) -> str:
        if not self.public_base_url:
            return key
        return f"{self.public_base_url}/{key}"


_storage_backend: StorageBackend | None = None
_storage_backend_by_provider: dict[str, StorageBackend] = {}


def get_storage_backend() -> StorageBackend:
    global _storage_backend
    if _storage_backend is not None:
        return _storage_backend

    _storage_backend = get_storage_backend_for_provider(settings.STORAGE_BACKEND)
    return _storage_backend


def get_storage_backend_for_provider(provider: str) -> StorageBackend:
    """
    Return a storage backend instance for the given provider.

    This allows per-resource providers (mixed local/oss in the same DB) while still
    supporting a default backend via `settings.STORAGE_BACKEND`.
    """
    key = (provider or "").lower().strip()
    if not key:
        raise ValueError("Storage provider is required")

    cached = _storage_backend_by_provider.get(key)
    if cached is not None:
        return cached

    if key == "local":
        base_dir = resolve_local_storage_dir()
        backend = LocalStorageBackend(base_dir, settings.LOCAL_STORAGE_BASE_URL)
        _storage_backend_by_provider[key] = backend
        return backend

    if key == "oss":
        backend = OSSStorageBackend(
            settings.OSS_ENDPOINT,
            settings.OSS_BUCKET,
            settings.OSS_ACCESS_KEY,
            settings.OSS_SECRET_KEY,
            settings.OSS_PUBLIC_BASE_URL,
        )
        _storage_backend_by_provider[key] = backend
        return backend

    raise ValueError(f"Unsupported storage backend provider: {provider}")
