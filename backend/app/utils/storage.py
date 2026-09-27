from pathlib import Path
import os
import socket
from typing import Dict, Optional
from minio import Minio
from dotenv import load_dotenv

load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "storyvoice_minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "storyvoice_minio_password")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() in {"true", "1", "t"}

def is_port_open(endpoint: str) -> bool:
    try:
        host, _, port_str = endpoint.partition(":")
        port = int(port_str) if port_str else (443 if MINIO_SECURE else 80)
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except Exception:
        return False

use_local_storage = not is_port_open(MINIO_ENDPOINT)
minio_client: Optional[Minio] = None

if not use_local_storage:
    try:
        minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
    except Exception as e:
        print(f"MinIO initialization failed: {e}. Falling back to local storage.")
        use_local_storage = True
else:
    print("MinIO port is closed. Using local storage fallback.")

IN_MEMORY_STORAGE: Dict[str, bytes] = {}
BUCKET_NAME = "storyvoice-audio"
LOCAL_STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage"

def ensure_bucket_exists() -> None:
    global use_local_storage
    if use_local_storage or minio_client is None:
        return
    try:
        if not minio_client.bucket_exists(BUCKET_NAME):
            minio_client.make_bucket(BUCKET_NAME)
    except Exception as e:
        print(f"MinIO bucket check failed: {e}. Switching to local storage.")
        use_local_storage = True

def _store_in_memory(file_path: str, object_name: str) -> None:
    try:
        IN_MEMORY_STORAGE[object_name] = Path(file_path).read_bytes()
    except Exception as e:
        print(f"Failed to read file for in-memory upload: {e}")

def upload_file(file_path: str, object_name: str) -> str:
    ensure_bucket_exists()
    if use_local_storage or minio_client is None:
        _store_in_memory(file_path, object_name)
        return f"/static/{object_name}"
    
    try:
        minio_client.fput_object(BUCKET_NAME, object_name, file_path)
        proto = "https" if MINIO_SECURE else "http"
        return f"{proto}://{MINIO_ENDPOINT}/{BUCKET_NAME}/{object_name}"
    except Exception as e:
        print(f"MinIO upload failed: {e}. Falling back to local storage.")
        _store_in_memory(file_path, object_name)
        return f"/static/{object_name}"




