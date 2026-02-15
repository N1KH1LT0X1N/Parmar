import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("VAPI_API_KEY", "")
headers = {"Authorization": f"Bearer {key}"}
base = "https://api.vapi.ai"

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
