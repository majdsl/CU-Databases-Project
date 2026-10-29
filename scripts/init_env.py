"""Create local credentials once; existing credentials are never overwritten."""
import os
from pathlib import Path
import secrets


def private_opener(path, flags):
    # Restrict POSIX permissions at creation, before any credentials are written.
    # On Windows the containing directory's ACL still controls access.
    return os.open(path, flags, 0o600)


def main():
    target = Path(__file__).resolve().parents[1] / ".env"
    try:
        with open(target, "x", encoding="utf-8", opener=private_opener) as stream:
            stream.write("CU_DB_ROOT_PASSWORD=" + secrets.token_hex(32) + "\n")
            stream.write("CU_DB_PASSWORD=" + secrets.token_hex(32) + "\n")
    except FileExistsError:
        print(".env already exists; keeping existing credentials.")
    else:
        print("Created .env with random local credentials. Do not commit or share it.")

if __name__ == "__main__":
    main()
