#!/usr/bin/env python3
"""
模拟 App SDK 调 /api/v1/cp/upgrade/check（带 HMAC 签名）

用法：
  uv run python scripts/cp_test_client.py \
    --base-url http://localhost:8000 \
    --app-id <tenant_uuid> \
    --hmac-secret <hmac_secret> \
    --version-code 100 \
    --channel direct \
    --device-id test-device-001 \
    --country ID
"""

import argparse
import base64
import hashlib
import hmac
import json
import sys
import time
import urllib.parse
import urllib.request


def main() -> int:
    ap = argparse.ArgumentParser(description="cp /upgrade/check test client")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--app-id", required=True, help="cp_apps.tenant_uuid")
    ap.add_argument("--hmac-secret", required=True, help="App SDK 内置的 hmac_secret")
    ap.add_argument("--version-code", type=int, default=1)
    ap.add_argument("--channel", default="direct")
    ap.add_argument("--device-id", default="test-device-001")
    ap.add_argument("--country", default="ID")
    args = ap.parse_args()

    params = {
        "app_id": args.app_id,
        "version_code": str(args.version_code),
        "channel": args.channel,
        "device_id": args.device_id,
        "country": args.country,
        "ts": str(int(time.time())),
    }

    # canonical = sorted("&".join(k=v))，排除 sig
    canonical = "&".join(f"{k}={params[k]}" for k in sorted(params.keys()))
    sig = base64.b64encode(
        hmac.new(args.hmac_secret.encode(), canonical.encode(), hashlib.sha256).digest()
    ).decode()
    params["sig"] = sig

    url = f"{args.base_url}/api/v1/cp/upgrade/check?{urllib.parse.urlencode(params)}"
    print(f"[GET] {url}\n")
    print(f"  canonical = {canonical}")
    print(f"  sig       = {sig}\n")

    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
            print(f"HTTP {r.status}")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}: {body}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
