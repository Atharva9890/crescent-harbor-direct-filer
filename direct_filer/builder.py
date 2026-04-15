from __future__ import annotations

import copy
from typing import Any

from .config import FilerConfig
from .utils import compute_eta, compute_manifest_id, isoformat_utc, utc_now


def build_manifest(scenario: dict[str, Any], config: FilerConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    now = utc_now()
    eta = compute_eta(int(scenario["_etaOffsetHours"]), now=now)
    manifest = copy.deepcopy(scenario)
    scenario_id = manifest.pop("_scenarioId")
    manifest.pop("_etaOffsetHours")

    manifest["manifestId"] = compute_manifest_id(scenario_id, eta)
    manifest["filer"] = {
        "filerId": config.filer_id,
        "legalName": config.legal_name,
        "contactEmail": config.contact_email,
    }
    manifest["arrival"]["eta"] = isoformat_utc(eta)
    manifest["vessel"]["name"] = manifest["vessel"]["name"].upper()
    manifest["filerSignature"] = {
        "signerName": config.signer_name,
        "signerTitle": config.signer_title,
        "signedAtUtc": isoformat_utc(now),
    }
    context = {
        "scenario_id": scenario_id,
        "built_at": now,
        "eta": eta,
    }
    return manifest, context
