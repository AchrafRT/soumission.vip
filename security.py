import hashlib, hmac, os, base64

def hash_password(password: str) -> str:
    salt=os.urandom(16)
    rounds=240_000
    digest=hashlib.pbkdf2_hmac('sha256', password.encode(), salt, rounds)
    return f'pbkdf2_sha256${rounds}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}'

def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, rounds, salt, digest = encoded.split('$',3)
        if algo!='pbkdf2_sha256': return False
        test=hashlib.pbkdf2_hmac('sha256', password.encode(), base64.b64decode(salt), int(rounds))
        return hmac.compare_digest(test, base64.b64decode(digest))
    except Exception:
        return False
