import hashlib


def load(path):
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    return text, hashlib.sha256(text.encode()).hexdigest()[:12]
