"""Single point where this repository reads its API keys.

Keys live in ``.env`` and nowhere else: no key is ever read from the
REDACTED repository, from a shell profile, or from a hard-coded default. Every
collection script (the migrated Gemini pipeline and the OpenAI / Perplexity
adapters that will follow) calls :func:`load_env` before touching a client, so
there is exactly one file to audit.

``load_env`` fills ``os.environ`` only for names that are not already set, which
keeps an explicit ``VAR=... python script.py`` working for one-off overrides.
Values are never printed.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def load_env(path: Path | None = None) -> dict[str, str]:
    """Parse ``.env`` into ``os.environ``. Returns the names it defined."""
    env_path = path or ENV_PATH
    defined: dict[str, str] = {}
    if not env_path.exists():
        return defined
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if name.startswith("export "):
            name = name[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not name or not value:
            continue
        defined[name] = value
        os.environ.setdefault(name, value)
    return defined


def require(name: str) -> str:
    """Return the key called ``name``, or exit with a message that never shows it."""
    load_env()
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(
            f"ERROR: {name} is empty. Paste it into {ENV_PATH} and rerun "
            f"(check it first with: .venv/bin/python check_keys.py)."
        )
    return value
