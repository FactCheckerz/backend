import hashlib
from pathlib import Path

def calculate_text_hash(text:str) -> str:
    """Calculates SHA-256 hash of text"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def calculate_file_hash(file_path:str,chunk_size: int = 1024*1024)->str:
    """Caluclates SHA-256 hash of file without loading whole file"""
    sha256 = hashlib.sha256()
    path = Path(file_path)
    with path.open("rb") as file:
        while chunk := file.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()