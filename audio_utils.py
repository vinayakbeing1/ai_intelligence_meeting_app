import os
import shutil
import uuid


def save_upload_file(upload_file):
    upload_dir = os.getenv("UPLOAD_DIR", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    extension = os.path.splitext(upload_file.filename)[1]
    path = os.path.join(upload_dir, f"{uuid.uuid4()}{extension}")

    with open(path, "wb") as f:
        shutil.copyfileobj(upload_file.file, f)
    return path
