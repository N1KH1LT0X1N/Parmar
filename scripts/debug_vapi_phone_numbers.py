import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402


settings = get_settings()
key = settings.vapi_api_key
headers = {"Authorization": f"Bearer {key}"}
base = settings.vapi_base_url.rstrip("/")

for path in ["/phone-number", "/phone-numbers", "/phoneNumber", "/phoneNumbers"]:
    url = base + path
    try:
        r = httpx.get(url, headers=headers, timeout=20)
        print(path, r.status_code)
        try:
            data = r.json()
            print(json.dumps(data, indent=2)[:2000])
        except Exception:
            print(r.text[:1000])
    except Exception as exc:
        print(path, "ERROR", str(exc))
