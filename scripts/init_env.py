"""Create local credentials once; existing credentials are never overwritten."""
from pathlib import Path
import secrets

def main():
    target = Path(__file__).resolve().parents[1] / ".env"
    try:
        with target.open("x", encoding="utf-8") as stream:
            stream.write("CU_DB_ROOT_PASSWORD=" + secrets.token_hex(32) + "\n")
            stream.write("CU_DB_PASSWORD=" + secrets.token_hex(32) + "\n")
    except FileExistsError:
        print(".env already exists; keeping existing credentials.")
    else:
        print("Created .env with random local credentials. Do not commit or share it.")

if __name__ == "__main__":
    main()
