from minio import Minio
import os
import shutil
import socket
from dotenv import load_dotenv

load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "storyvoice_minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "storyvoice_minio_password")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() in ('true', '1', 't')

def is_port_open(endpoint: str) -> bool:
    try:
        if ":" in endpoint:
            host, port_str = endpoint.split(":")
            port = int(port_str)
        else:
            host = endpoint
            port = 443 if MINIO_SECURE else 80
        
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except Exception:
        return False

use_local_storage = not is_port_open(MINIO_ENDPOINT)
minio_client = None

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

BUCKET_NAME = "storyvoice-audio"
LOCAL_STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage")

def ensure_bucket_exists():
    global use_local_storage
    if use_local_storage:
        os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)
        return
    try:
        found = minio_client.bucket_exists(BUCKET_NAME)
        if not found:
            minio_client.make_bucket(BUCKET_NAME)
    except Exception as e:
        print(f"MinIO bucket check failed: {e}. Switching to local storage.")
        use_local_storage = True
        os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)

def upload_file(file_path: str, object_name: str):
    ensure_bucket_exists()
    if use_local_storage:
        dest_path = os.path.join(LOCAL_STORAGE_DIR, object_name)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(file_path, dest_path)
        return f"/static/{object_name}"
    
    try:
        minio_client.fput_object(BUCKET_NAME, object_name, file_path)
        proto = "https" if MINIO_SECURE else "http"
        return f"{proto}://{MINIO_ENDPOINT}/{BUCKET_NAME}/{object_name}"
    except Exception as e:
        print(f"MinIO upload failed: {e}. Falling back to local storage.")
        dest_path = os.path.join(LOCAL_STORAGE_DIR, object_name)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(file_path, dest_path)
        return f"/static/{object_name}"


