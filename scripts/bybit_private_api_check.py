#!/usr/bin/env python3
"""Verify Bybit V5 HMAC credentials using the read-only API-key-info endpoint.

This script performs one authenticated GET request to /v5/user/query-api.
It never prints the API key, API secret, signature, or full response payload.
It does not call trading, wallet-transfer, or withdrawal endpoints.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

ENDPOINT = "/v5/user/query-api"
RECV_WINDOW = "5000"


def make_signature(timestamp: str, api_key: str, api_secret: str,
                   recv_window: str = RECV_WINDOW) -> str:
    payload = f"{timestamp}{api_key}{recv_window}"
    return hmac.new(
        api_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_headers(api_key: str, api_secret: str,
                  timestamp: str | None = None) -> dict[str, str]:
    timestamp = timestamp or str(int(time.time() * 1000))
    return {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": RECV_WINDOW,
        "X-BAPI-SIGN": make_signature(timestamp, api_key, api_secret),
        "Content-Type": "application/json",
        "User-Agent": "bybit-trading-bot-readonly-check/1.0",
    }


def verify_response(payload: dict[str, Any], api_key: str) -> tuple[bool, str]:
    if payload.get("retCode") != 0:
        code = payload.get("retCode", "unknown")
        message = str(payload.get("retMsg", "Bybit returned an error"))
        return False, f"Bybit rejected the request (retCode={code}, retMsg={message})."

    result = payload.get("result")
    if not isinstance(result, dict):
        return False, "Bybit response has no valid result object."
    if result.get("apiKey") != api_key:
        return False, "The authenticated response did not match the configured API key."
    if result.get("readOnly") != 1:
        return False, "SECURITY CHECK FAILED: this API key is not marked read-only."

    permissions = result.get("permissions")
    if isinstance(permissions, dict):
        trade_permissions = []
        for category in ("ContractTrade", "Spot", "Options", "Derivatives"):
            values = permissions.get(category, [])
            if isinstance(values, list) and values:
                trade_permissions.extend(f"{category}:{value}" for value in values)
        if trade_permissions:
            return False, (
                "SECURITY CHECK FAILED: trade permissions are present despite "
                "the readOnly flag. Revoke this key and create a strictly read-only key."
            )

    return True, "Authenticated successfully; API key is marked read-only."


def main() -> int:
    key_from_env = os.environ.get("BYBIT_API_KEY", "")
    secret_from_env = os.environ.get("BYBIT_API_SECRET", "")
    base_url = os.environ.get("BYBIT_API_BASE_URL", "https://api.bybit.kz").rstrip("/")

    if not key_from_env or not secret_from_env:
        print("Missing required GitHub Secrets: BYBIT_API_KEY and/or BYBIT_API_SECRET.")
        return 2
    if not base_url.startswith("https://"):
        print("Invalid API base URL: HTTPS is required.")
        return 2

    headers = build_headers(key_from_env, secret_from_env)
    request = urllib.request.Request(
        f"{base_url}{ENDPOINT}",
        headers=headers,
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"Bybit HTTP request failed with status {exc.code}; response body was suppressed.")
        if exc.code == 403:
            print("Check the regional API host and whether the runner's network/IP is restricted.")
        return 1
    except urllib.error.URLError as exc:
        reason_type = type(exc.reason).__name__
        print(f"Could not reach Bybit API ({reason_type}); no credential values were logged.")
        return 1
    except (TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        print("Bybit request timed out or returned an invalid response; response body was suppressed.")
        return 1

    ok, message = verify_response(payload, key_from_env)
    print(message)
    if not ok:
        return 1

    result = payload["result"]
    print(f"Read-only flag: {result.get('readOnly')}")
    print(f"IP binding configured: {bool(result.get('ips'))}")
    print("No orders, transfers, withdrawals, or account mutations were requested.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
