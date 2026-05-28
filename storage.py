import os, json, io, tarfile, logging, datetime, tempfile
from typing import Any

logger = logging.getLogger("brain.storage")

# Google Cloud Storage is only available inside Replit (sidecar-based auth).
# On self-hosted deployments (Vultr etc.) these imports are absent and all
# object-storage operations silently no-op — local JSON files are the source
# of truth there instead.
_GCS_AVAILABLE = False
_requests = None
_gcs = None
_credentials_base = object

try:
    import requests as _requests
    from google.auth import credentials as _google_auth_creds
    from google.cloud import storage as _gcs
    _credentials_base = _google_auth_creds.Credentials
    _GCS_AVAILABLE = True
except ImportError:
    logger.info("google-cloud-storage not available — object storage disabled (local-file mode)")

SIDECAR = "http://127.0.0.1:1106"
BUCKET_ID = os.getenv("DEFAULT_OBJECT_STORAGE_BUCKET_ID", "").strip()


class _SidecarCredentials(_credentials_base):
    """Fetches Google access tokens from the Replit sidecar proxy."""

    def refresh(self, request):
        try:
            resp = _requests.post(
                f"{SIDECAR}/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                    "audience": "replit",
                    "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
                    "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
                    "subject_token": "dummy",
                },
                timeout=10,
            )
            data = resp.json()
            self.token = data["access_token"]
            expires_in = int(data.get("expires_in", 3600))
            self.expiry = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in - 60)
        except Exception as e:
            raise RuntimeError(f"Sidecar token fetch failed: {e}") from e


_gcs_client = None
_bucket = None


def _get_bucket():
    global _gcs_client, _bucket
    if not _GCS_AVAILABLE:
        raise RuntimeError("google-cloud-storage not installed")
    if _bucket is not None:
        return _bucket
    if not BUCKET_ID:
        raise RuntimeError("DEFAULT_OBJECT_STORAGE_BUCKET_ID is not set")
    creds = _SidecarCredentials()
    creds.refresh(None)
    _gcs_client = _gcs.Client(credentials=creds, project="replit")
    _bucket = _gcs_client.bucket(BUCKET_ID)
    return _bucket


def load_blob(key: str, default: Any = None) -> Any:
    """Download a JSON blob from object storage by key. Returns default on miss."""
    if not _GCS_AVAILABLE:
        return default
    try:
        bucket = _get_bucket()
        blob = bucket.blob(key)
        data = blob.download_as_bytes()
        return json.loads(data.decode("utf-8"))
    except Exception as e:
        msg = str(e)
        if "404" in msg or "does not exist" in msg.lower() or "Not Found" in msg or "No such object" in msg:
            return default
        logger.warning("load_blob failed key=%s: %s", key, e)
        return default


def save_blob(key: str, data: Any) -> None:
    """Upload data serialized as JSON to object storage."""
    if not _GCS_AVAILABLE:
        return
    try:
        bucket = _get_bucket()
        blob = bucket.blob(key)
        payload = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        blob.upload_from_string(payload, content_type="application/json")
    except Exception as e:
        logger.warning("save_blob failed key=%s: %s", key, e)


def list_blobs_with_prefix(prefix: str) -> list[str]:
    """Return all blob keys under the given prefix."""
    if not _GCS_AVAILABLE:
        return []
    try:
        bucket = _get_bucket()
        client = _gcs_client
        return [b.name for b in client.list_blobs(bucket, prefix=prefix)]
    except Exception as e:
        logger.warning("list_blobs failed prefix=%s: %s", prefix, e)
        return []


def upload_tar(key: str, directory: str) -> None:
    """Tar the given directory and upload as a single blob."""
    if not _GCS_AVAILABLE:
        return
    try:
        bucket = _get_bucket()
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with tarfile.open(tmp_path, mode="w:gz") as tar:
                tar.add(directory, arcname=os.path.basename(directory))
            size = os.path.getsize(tmp_path)
            blob = bucket.blob(key)
            blob.upload_from_filename(tmp_path, content_type="application/gzip")
            logger.info("upload_tar: %s -> %s (%d bytes)", directory, key, size)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception as e:
        logger.warning("upload_tar failed key=%s dir=%s: %s", key, directory, e)


def download_tar(key: str, parent_dir: str) -> bool:
    """Download a tar blob and unpack it into parent_dir. Returns True on success."""
    if not _GCS_AVAILABLE:
        return False
    try:
        bucket = _get_bucket()
        blob = bucket.blob(key)
        buf = io.BytesIO()
        blob.download_to_file(buf)
        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            tar.extractall(path=parent_dir)
        logger.info("download_tar: %s unpacked to %s", key, parent_dir)
        return True
    except Exception as e:
        msg = str(e)
        if "404" in msg or "does not exist" in msg.lower() or "Not Found" in msg or "No such object" in msg:
            logger.info("download_tar: no snapshot found for %s (fresh start)", key)
        else:
            logger.warning("download_tar failed key=%s: %s", key, e)
        return False


def delete_blob(key: str) -> None:
    """Delete a blob from object storage."""
    if not _GCS_AVAILABLE:
        return
    try:
        bucket = _get_bucket()
        bucket.blob(key).delete()
    except Exception as e:
        logger.warning("delete_blob failed key=%s: %s", key, e)
