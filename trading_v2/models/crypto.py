# coding: utf-8
"""Encryption helpers for locally persisted provider credentials."""

import os
from pathlib import Path


def encrypt_secret(secret: str) -> str:
    """Encrypt a secret at rest using the local Fernet key."""
    from cryptography.fernet import Fernet

    path = Path(os.getenv("TRADING_V2_MODEL_SECRET_KEY_FILE", "data/model-secret.key"))
    if path.exists():
        key = path.read_bytes()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        try:
            with path.open("xb") as key_file:
                key_file.write(key)
        except FileExistsError:
            key = path.read_bytes()
    return Fernet(key).encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_secret(secret: str) -> str:
    """Decrypt a stored secret for backend-only use."""
    from cryptography.fernet import Fernet

    path = Path(os.getenv("TRADING_V2_MODEL_SECRET_KEY_FILE", "data/model-secret.key"))
    key = path.read_bytes()
    return Fernet(key).decrypt(secret.encode("ascii")).decode("utf-8")
