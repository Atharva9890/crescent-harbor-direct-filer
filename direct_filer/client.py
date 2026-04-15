from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import FilerConfig
from .utils import canonical_json_bytes, hmac_hex, sha256_hex


@dataclass(frozen=True)
class SubmissionResult:
    status: str
    receipt_id: str | None = None
    manifest_id: str | None = None
    errors: list[dict] | None = None


class AuthorityClient:
    def __init__(self, config: FilerConfig) -> None:
        self.config = config

    def submit_manifest(self, manifest: dict) -> SubmissionResult:
        body = canonical_json_bytes(manifest)
        response = self._request("POST", "/v3/manifests", body)
        payload = json.loads(response)
        return SubmissionResult(
            status=payload["status"],
            receipt_id=payload["receiptId"],
            manifest_id=payload["manifestId"],
        )

    def poll_ack(self, receipt_id: str) -> SubmissionResult:
        deadline = time.time() + self.config.poll_timeout_seconds
        while time.time() < deadline:
            response = self._request("GET", f"/v3/acks/{receipt_id}", b"")
            payload = json.loads(response)
            if payload["status"] == "PENDING":
                time.sleep(self.config.poll_interval_seconds)
                continue
            return SubmissionResult(
                status=payload["status"],
                receipt_id=payload.get("receiptId"),
                manifest_id=payload.get("manifestId"),
                errors=payload.get("errors"),
            )
        raise TimeoutError(f"ack {receipt_id} did not reach a terminal state within {self.config.poll_timeout_seconds} seconds")

    def _request(self, method: str, path: str, body: bytes) -> str:
        timestamp = str(int(time.time()))
        signature = hmac_hex(
            self.config.shared_secret,
            "\n".join(["CHCAv3", method, path, timestamp, sha256_hex(body)]),
        )
        request = urllib.request.Request(
            url=f"{self.config.authority_base_url}{path}",
            data=body if method == "POST" else None,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-Crescent-FilerId": self.config.filer_id,
                "X-Crescent-Timestamp": timestamp,
                "X-Crescent-Signature": signature,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8")
            raise RuntimeError(f"authority returned HTTP {exc.code}: {payload}") from exc
