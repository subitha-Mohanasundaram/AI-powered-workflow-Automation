import json
import os
import sys
import time

import requests


def main() -> int:
    n8n_base = os.environ.get("N8N_BASE", "http://127.0.0.1:5678").rstrip("/")
    api_base = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")

    n8n_user = os.environ.get("N8N_BASIC_USER", "admin")
    n8n_pass = os.environ.get("N8N_BASIC_PASSWORD", "admin")

    trigger_payload = {
        "service_name": os.environ.get("SERVICE_NAME", "payment-service"),
        "reason": os.environ.get("REASON", "demo_trigger")
    }

    resp = requests.post(
        f"{n8n_base}/webhook/incident-trigger",
        json=trigger_payload,
        auth=(n8n_user, n8n_pass),
        timeout=60
    )
    resp.raise_for_status()

    print("n8n response:")
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)

    time.sleep(1)
    incidents = requests.get(f"{api_base}/incidents", timeout=30)
    incidents.raise_for_status()
    data = incidents.json()
    latest = data[0] if isinstance(data, list) and data else None

    print("\nlatest incident:")
    print(json.dumps(latest, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
