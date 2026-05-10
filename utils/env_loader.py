import os
from pathlib import Path

def get_github_token() -> str | None:
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token

    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return None

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("GITHUB_TOKEN="):
                token = line.split("=", 1)[1].strip()
                if token:
                    return token
    return None