from minio import Minio
import os
from dotenv import load_dotenv

load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "storyvoice_minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "storyvoice_minio_password")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() in ('true', '1', 't')

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)

BUCKET_NAME = "storyvoice-audio"

def ensure_bucket_exists():
    found = minio_client.bucket_exists(BUCKET_NAME)
    if not found:
        minio_client.make_bucket(BUCKET_NAME)

def upload_file(file_path: str, object_name: str):
    ensure_bucket_exists()
    minio_client.fput_object(BUCKET_NAME, object_name, file_path)
    return f"http://{MINIO_ENDPOINT}/{BUCKET_NAME}/{object_name}"
