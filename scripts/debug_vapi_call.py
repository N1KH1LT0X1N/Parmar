import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402


settings = get_settings()

payload = {
    "assistantId": settings.vapi_assistant_id,
    "phoneNumberId": settings.vapi_phone_number_id,
    "customer": {
        "number": "+919867477169",
        "name": "Nikhil Pise",
    },
    "assistantOverrides": {
        "variableValues": {
            "name": "Nikhil Pise",
            "location": "Mumbai",
            "budget_range": "2-3Cr",
            "bhk_preference": "2BHK",
        }
    },
}

headers = {
    "Authorization": f"Bearer {settings.vapi_api_key}",
    "Content-Type": "application/json",
}

url = settings.vapi_api_url

print("URL:", url)
print("assistantId set:", bool(payload["assistantId"]))
print("phoneNumberId set:", bool(payload["phoneNumberId"]))
print("api key set:", bool(settings.vapi_api_key))

with httpx.Client(timeout=30) as client:
    response = client.post(url, json=payload, headers=headers)

print("status:", response.status_code)
try:
    print(json.dumps(response.json(), indent=2))
except Exception:
    print(response.text)
