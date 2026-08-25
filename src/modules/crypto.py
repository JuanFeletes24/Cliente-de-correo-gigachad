import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken

def _get_fernet(key: str) -> Fernet:
    # We hash the string key to a 32-byte key to make sure it's valid for Fernet
    # Then we url-safe base64 encode it.
    hasher = hashlib.sha256()
    hasher.update(key.encode('utf-8'))
    fernet_key = base64.urlsafe_b64encode(hasher.digest())
    return Fernet(fernet_key)

def encrypt_message(message: str, key: str) -> str:
    """Encrypts a string message using a symmetric key."""
    if not message or not key:
        return message
    try:
        f = _get_fernet(key)
        encrypted = f.encrypt(message.encode('utf-8'))
        return encrypted.decode('utf-8')
    except Exception as e:
        print(f"Error encrypting message: {e}")
        return message

def decrypt_message(encrypted_message: str, key: str) -> str:
    """Decrypts a string message using a symmetric key."""
    if not encrypted_message or not key:
        return encrypted_message
    try:
        f = _get_fernet(key)
        decrypted = f.decrypt(encrypted_message.encode('utf-8'))
        return decrypted.decode('utf-8')
    except InvalidToken:
        return encrypted_message  # Return original if unable to decrypt (might not be encrypted for this key)
    except Exception as e:
        print(f"Error decrypting message: {e}")
        return encrypted_message
