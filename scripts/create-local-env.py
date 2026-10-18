"""Create local development credentials without printing or overwriting them."""

import secrets
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    destination = root / ".env"
    if destination.exists():
        print("A local .env already exists; it was left unchanged.")
        return
    content = (root / ".env.example").read_text(encoding="utf-8")
    content = content.replace(
        "replace-with-a-long-random-key", secrets.token_urlsafe(64)
    )
    content = content.replace(
        "replace-with-a-random-local-password", secrets.token_urlsafe(32)
    )
    with destination.open("x", encoding="utf-8") as output:
        output.write(content)
    print(
        "Created ignored .env with unique local credentials. No secret values were printed."
    )


if __name__ == "__main__":
    main()
