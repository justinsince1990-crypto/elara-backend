"""Local filesystem storage backend for self-hosted deployments.

Drop-in replacement for storage.py (Replit GCS sidecar).
All data lives on disk under DATA_DIR (default: ./data/).
"""

import os, json, io, tarfile, logging, shutil
from typing import Any

logger = logging.getLogger("brain.storage")

DATA_DIR = os.getenv("ELARA_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(DATA_DIR, exist_ok=True)


def _key_path(key: str) -> str:
    full = os.path.join(DATA_DIR, key)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    return full


def load_blob(key: str, default: Any = None) -> Any:
    path = _key_path(key)
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("load_blob failed key=%s: %s", key, e)
        return default


def save_blob(key: str, data: Any) -> None:
    path = _key_path(key)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning("save_blob failed key=%s: %s", key, e)


def list_blobs_with_prefix(prefix: str) -> list[str]:
    base = os.path.join(DATA_DIR, prefix)
    parent = os.path.dirname(base)
    if not os.path.isdir(parent):
        return []
    results = []
    for root, _, files in os.walk(parent):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, DATA_DIR)
            if rel.startswith(prefix):
                results.append(rel)
    return results


def upload_tar(key: str, directory: str) -> None:
    path = _key_path(key)
    try:
        with tarfile.open(path, mode="w:gz") as tar:
            tar.add(directory, arcname=os.path.basename(directory))
        logger.info("upload_tar: %s -> %s", directory, path)
    except Exception as e:
        logger.warning("upload_tar failed key=%s dir=%s: %s", key, directory, e)


def download_tar(key: str, parent_dir: str) -> bool:
    path = _key_path(key)
    if not os.path.exists(path):
        logger.info("download_tar: no snapshot found for %s", key)
        return False
    try:
        with tarfile.open(path, mode="r:gz") as tar:
            tar.extractall(path=parent_dir)
        logger.info("download_tar: %s unpacked to %s", key, parent_dir)
        return True
    except Exception as e:
        logger.warning("download_tar failed key=%s: %s", key, e)
        return False


def delete_blob(key: str) -> None:
    path = _key_path(key)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.warning("delete_blob failed key=%s: %s", key, e)
