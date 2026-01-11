"""
Encryption Service

AES-256 encryption for sensitive data like MT5 credentials.
Uses PBKDF2 key derivation and Fernet symmetric encryption.
"""

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from archon_prime.api.config import settings


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data.

    Uses AES-256 via Fernet with PBKDF2 key derivation.
    Each encryption includes a unique salt for added security.
    """

    SALT_SIZE = 16  # 128 bits
    ITERATIONS = 480000  # OWASP recommended

    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize encryption service.

        Args:
            master_key: Master encryption key. Uses settings if not provided.
        """
        self._master_key = (master_key or settings.MASTER_ENCRYPTION_KEY).encode()

    def _derive_key(self, salt: bytes) -> bytes:
        """
        Derive a Fernet-compatible key from master key and salt.

        Args:
            salt: Random salt for key derivation

        Returns:
            32-byte key encoded as base64 for Fernet
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.ITERATIONS,
        )
        key = kdf.derive(self._master_key)
        return base64.urlsafe_b64encode(key)

    def encrypt(self, plaintext: str) -> bytes:
        """
        Encrypt a string value.

        Args:
            plaintext: String to encrypt

        Returns:
            Encrypted bytes (salt + ciphertext)
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty string")

        # Generate random salt
        salt = os.urandom(self.SALT_SIZE)

        # Derive key and encrypt
        key = self._derive_key(salt)
        fernet = Fernet(key)
        ciphertext = fernet.encrypt(plaintext.encode())

        # Prepend salt to ciphertext
        return salt + ciphertext

    def decrypt(self, encrypted_data: bytes) -> str:
        """
        Decrypt encrypted data.

        Args:
            encrypted_data: Encrypted bytes (salt + ciphertext)

        Returns:
            Decrypted string

        Raises:
            ValueError: If decryption fails
        """
        if not encrypted_data or len(encrypted_data) <= self.SALT_SIZE:
            raise ValueError("Invalid encrypted data")

        # Extract salt and ciphertext
        salt = encrypted_data[: self.SALT_SIZE]
        ciphertext = encrypted_data[self.SALT_SIZE :]

        # Derive key and decrypt
        key = self._derive_key(salt)
        fernet = Fernet(key)

        try:
            plaintext = fernet.decrypt(ciphertext)
            return plaintext.decode()
        except InvalidToken:
            raise ValueError("Decryption failed - invalid key or corrupted data")

    def rotate_encryption(self, encrypted_data: bytes, new_master_key: str) -> bytes:
        """
        Re-encrypt data with a new master key.

        Args:
            encrypted_data: Data encrypted with current master key
            new_master_key: New master key to use

        Returns:
            Data encrypted with new master key
        """
        # Decrypt with current key
        plaintext = self.decrypt(encrypted_data)

        # Re-encrypt with new key
        new_service = EncryptionService(new_master_key)
        return new_service.encrypt(plaintext)


# Singleton instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Get singleton encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
