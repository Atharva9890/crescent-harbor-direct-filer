from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(tz=UTC).replace(microsecond=0)


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_eta(offset_hours: int, now: datetime | None = None) -> datetime:
    base = now or utc_now()
    return base + timedelta(hours=offset_hours)


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def hmac_hex(secret: str, value: str) -> str:
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def quantize_cents(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def has_more_than_two_decimal_places(value: Any) -> bool:
    decimal_value = Decimal(str(value)).normalize()
    return decimal_value.as_tuple().exponent < -2


def age_on_date(date_of_birth: str, on_date: datetime) -> int:
    dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
    arrival_date = on_date.date()
    years = arrival_date.year - dob.year
    if (arrival_date.month, arrival_date.day) < (dob.month, dob.day):
        years -= 1
    return years


def compute_manifest_id(scenario_id: str, eta: datetime) -> str:
    digest = hashlib.sha256(f"{scenario_id}:{isoformat_utc(eta)}".encode("utf-8")).hexdigest()
    return f"CH-{digest[:22].upper()}"
