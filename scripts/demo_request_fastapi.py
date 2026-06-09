import json
import os
import sys

import requests


def main() -> int:
    api_base = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")
    api_key = os.environ.get("API_ACCESS_KEY", "")

    payload = {
        "user_id": os.environ.get("DEMO_USER_ID", "demo-user@example.com"),
        "request_text": os.environ.get(
            "DEMO_REQUEST_TEXT",
            "Investigate payment failures and send incident report to dashboard",
        ),
    }

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    resp = requests.post(f"{api_base}/api/requests", headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    print(json.dumps(resp.json(), indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

