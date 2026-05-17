import bcrypt

class Encryptation:
    @staticmethod
    def hash_password(password: str) -> bytes:
        """Hash a password for storing."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed

    @staticmethod
    def check_password(password: str, hashed: bytes) -> bool:
        """Check a password against an existing hash."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed)