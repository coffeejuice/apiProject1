import bcrypt


def hash_password(password: str) -> bytes:
    # Convert the password string to bytes
    password_bytes = password.encode('utf-8')
    # Generate a random salt
    salt = bcrypt.gensalt()
    # Hash the password with the salt
    hashed_password = bcrypt.hashpw(password_bytes, salt)
    return hashed_password


def verify_password(password: str, hashed_password: bytes) -> bool:
    # Convert the password string to bytes
    password_bytes = password.encode('utf-8')
    # Verify the password against the hashed password
    try:
        is_valid = bcrypt.checkpw(password_bytes, hashed_password)
        return is_valid
    except ValueError:
        return False


def hash_and_test_password(password: str) -> [bytes, bool]:
    # Convert the password string to bytes
    hashed_password = hash_password(password)
    # Verify the password
    is_valid = verify_password(password, hashed_password)
    return hashed_password, is_valid
