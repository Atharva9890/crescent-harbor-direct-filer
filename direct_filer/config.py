from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class FilerConfig:
    filer_id: str
    legal_name: str
    contact_email: str
    signer_name: str
    signer_title: str
    shared_secret: str
    authority_base_url: str
    poll_interval_seconds: float
    poll_timeout_seconds: float


def load_config() -> FilerConfig:
    secret_path = Path(
        os.environ.get("CRESCENT_SECRET_PATH", ROOT / "mock-customs" / "secrets.json")
    )
    with secret_path.open() as handle:
        secrets = json.load(handle)

    filer_id = os.environ.get("CRESCENT_FILER_ID", "CHC100001")
    return FilerConfig(
        filer_id=filer_id,
        legal_name=os.environ.get("CRESCENT_LEGAL_NAME", "Crescent Harbor Direct Filer"),
        contact_email=os.environ.get("CRESCENT_CONTACT_EMAIL", "ops@crescentharborfiler.example"),
        signer_name=os.environ.get("CRESCENT_SIGNER_NAME", "Atharva Kalange"),
        signer_title=os.environ.get("CRESCENT_SIGNER_TITLE", "Software Engineer"),
        shared_secret=secrets[filer_id],
        authority_base_url=os.environ.get("CRESCENT_AUTHORITY_BASE_URL", "http://localhost:8080"),
        poll_interval_seconds=float(os.environ.get("CRESCENT_POLL_INTERVAL_SECONDS", "2")),
        poll_timeout_seconds=float(os.environ.get("CRESCENT_POLL_TIMEOUT_SECONDS", "60")),
    )
