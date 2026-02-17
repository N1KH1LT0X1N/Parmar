# Contributing Runbook

This runbook helps teammates make safe changes quickly.

## Branch and Commit Strategy

- Create feature branch from latest default branch
- Keep PR scope small (backend or frontend, not both when possible)
- Include test evidence in PR description

## Local Setup

1. Copy `.env.example` to `.env`
2. Fill provider credentials (Vapi/Twilio)
3. Install dependencies:
   - Backend: `python -m pip install -r backend/requirements.txt`
   - Frontend: `cd frontend && npm install`

## Start Services

- Recommended: `powershell -ExecutionPolicy Bypass -File scripts/start-demo.ps1`
- Strict env validation: `... -ValidationMode strict`

## Test Checklist Before PR

- Backend unit/integration tests pass:
  - `python -m pytest backend/tests -q`
- Frontend tests + build pass:
  - `cd frontend && npm run test && npm run build`
- Runtime smoke:
  - `GET /diagnostics/vapi-preflight`
  - `GET /manager-status`
  - `POST /upload` with a sample CSV
  - `POST /start-campaign`

## Coding Notes

- Keep API responses backward compatible where possible
- Do not hardcode secrets or credentials
- Use environment-driven config only
- CSV phone values are normalized to E.164 where possible (India defaults supported)
- Webhook processing is idempotent for duplicate end-of-call payloads
- Preserve existing lead statuses:
  - `pending`, `queued`, `calling`, `completed`, `failed`, `voicemail`

## Known Demo Constraints

- Twilio trial voice prompt may require recipient keypress
- WhatsApp sandbox requires recipient join code
- Real call completion depends on provider webhook timing

## Vapi Webhook Setup (Important)

- Configure webhook target in Vapi assistant/dashboard settings.
- Do not include `webhookUrl` in per-call `POST /call` payloads; Vapi rejects it with `400`.
- Use backend endpoint `POST /webhook/vapi` for end-of-call processing.

## Local Development Modes

- **Mode A — Call-init only (no deployed backend):**
  - Set `VAPI_REQUIRE_ASSISTANT_SERVER_CONFIG=false` in `.env`.
  - Keep `VAPI_PREFLIGHT_REQUIRED_FOR_CAMPAIGN=true` to validate assistant + phone number IDs.
  - Expect leads to move to `calling`, but not auto-complete without webhook events.

- **Mode B — Full lifecycle locally:**
  - Use tunnel (for example `ngrok http 8000`) and set Vapi server URL to `https://<tunnel>/webhook/vapi`.
  - Set `VAPI_REQUIRE_ASSISTANT_SERVER_CONFIG=true`.
  - Confirm `GET /diagnostics/vapi-preflight` returns `ok=true` before campaigns.

## Useful Files

- Backend entry: `backend/app/main.py`
- Vapi integration: `backend/app/services/vapi.py`
- Twilio integration: `backend/app/services/twilio_service.py`
- Frontend dashboard: `frontend/src/App.jsx`
- Prompt settings: `docs/vapi-system-prompt.md`
