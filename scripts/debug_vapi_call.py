import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

payload = {
    "assistantId": os.getenv("VAPI_ASSISTANT_ID", ""),
    "phoneNumberId": os.getenv("VAPI_PHONE_NUMBER_ID", ""),
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
    "Authorization": f"Bearer {os.getenv('VAPI_API_KEY', '')}",
    "Content-Type": "application/json",
}

url = os.getenv("VAPI_API_URL", "https://api.vapi.ai/call")

print("URL:", url)
print("assistantId set:", bool(payload["assistantId"]))
print("phoneNumberId set:", bool(payload["phoneNumberId"]))
print("api key set:", bool(os.getenv("VAPI_API_KEY")))

with httpx.Client(timeout=30) as client:
    response = client.post(url, json=payload, headers=headers)

print("status:", response.status_code)
try:
    print(json.dumps(response.json(), indent=2))
except Exception:
    print(response.text)
