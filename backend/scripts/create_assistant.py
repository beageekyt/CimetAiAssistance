"""Creates or PATCHes the Vapi assistant with the current prompt/tools.

Usage:
    python scripts/create_assistant.py https://<public-https-backend-url>
    python scripts/create_assistant.py https://<public-https-backend-url> --new   # force a new assistant

On first run (no VAPI_ASSISTANT_ID in .env) this creates a new assistant and
writes the id back into backend/.env and frontend/.env. On later runs it
PATCHes the existing assistant so the id stays stable.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings  # noqa: E402
from app.journey.prompt import build_assistant_payload  # noqa: E402

BACKEND_ENV = Path(__file__).parent.parent / ".env"
FRONTEND_ENV = Path(__file__).parent.parent.parent / "frontend" / ".env"


def _set_env_var(path: Path, key: str, value: str) -> None:
    if not path.exists():
        path.write_text(f"{key}={value}\n", encoding="utf-8")
        return
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^{key}=.*$", re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub(f"{key}={value}", text)
    else:
        text = text.rstrip("\n") + f"\n{key}={value}\n"
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_assistant.py https://<public-https-backend-url> [--new]")
        sys.exit(1)

    server_url = sys.argv[1]
    force_new = "--new" in sys.argv[2:]

    settings = get_settings()
    if not settings.vapi_api_key:
        print("VAPI_API_KEY is not set in backend/.env")
        sys.exit(1)

    payload = build_assistant_payload(
        server_base_url=server_url,
        human_agent_name=settings.human_agent_name,
        human_handoff_number=settings.human_handoff_number,
        webhook_secret=settings.vapi_webhook_secret,
    )
    headers = {"Authorization": f"Bearer {settings.vapi_api_key}"}

    with httpx.Client(timeout=30) as client:
        if settings.vapi_assistant_id and not force_new:
            resp = client.patch(
                f"{settings.vapi_base_url}/assistant/{settings.vapi_assistant_id}",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            print(f"Patched assistant {settings.vapi_assistant_id}")
        else:
            resp = client.post(f"{settings.vapi_base_url}/assistant", headers=headers, json=payload)
            resp.raise_for_status()
            assistant_id = resp.json()["id"]
            print(f"Created assistant {assistant_id}")
            _set_env_var(BACKEND_ENV, "VAPI_ASSISTANT_ID", assistant_id)
            _set_env_var(FRONTEND_ENV, "VITE_VAPI_ASSISTANT_ID", assistant_id)
            print("Wrote VAPI_ASSISTANT_ID to backend/.env and frontend/.env")


if __name__ == "__main__":
    main()
