import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptionManager:
    """AES-256-GCM encryption for CeFi API credentials."""

    def __init__(self):
        from app.config import get_settings
        self.settings = get_settings()
        self._key: bytes | None = None

    def _get_key(self) -> bytes:
        if self._key is None:
            if not self.settings.ENCRYPTION_KEY:
                raise ValueError("ENCRYPTION_KEY not set in environment")
            self._key = base64.b64decode(self.settings.ENCRYPTION_KEY)
            if len(self._key) != 32:
                raise ValueError("ENCRYPTION_KEY must be 32 bytes (44 base64 chars)")
        return self._key

    def encrypt(self, plaintext: str) -> str:
        """Encrypt string, return base64 encoded ciphertext:nonce"""
        key = self._get_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return f"{base64.b64encode(ciphertext).decode()}:{base64.b64encode(nonce).decode()}"

    def decrypt(self, encrypted: str) -> str:
        """Decrypt base64 encoded ciphertext:nonce"""
        key = self._get_key()
        aesgcm = AESGCM(key)
        try:
            ciphertext_b64, nonce_b64 = encrypted.split(":")
            ciphertext = base64.b64decode(ciphertext_b64)
            nonce = base64.b64decode(nonce_b64)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode()
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")


encryption_manager = EncryptionManager()


def encrypt_credentials(api_key: str, api_secret: str, passphrase: str | None = None) -> dict:
    result = {
        "api_key": encryption_manager.encrypt(api_key),
        "api_secret": encryption_manager.encrypt(api_secret),
    }
    if passphrase:
        result["passphrase"] = encryption_manager.encrypt(passphrase)
    return result


def decrypt_credentials(encrypted: dict) -> dict:
    result = {
        "api_key": encryption_manager.decrypt(encrypted["api_key"]),
        "api_secret": encryption_manager.decrypt(encrypted["api_secret"]),
    }
    if "passphrase" in encrypted:
        result["passphrase"] = encryption_manager.decrypt(encrypted["passphrase"])
    return result