# Parmar AI Calling Agent

Production-style outbound lead qualification stack:

- `backend/`: FastAPI + SQLModel API, durable campaign queue, webhook processing
- `frontend/`: React + Vite dashboard
- `docs/`: prompts and runbooks

## Quick Start

## 1. Prerequisites

- Python 3.10+
- Node.js 18+
- Vapi account (assistant + phone number)
- Twilio account (for manager notifications)

## 2. Environment

- Copy `.env.example` to `.env`
- Fill required keys:
  - `VAPI_API_KEY` (or `VAPI_PRIVATE_KEY`)
  - `VAPI_ASSISTANT_ID`
  - `VAPI_PHONE_NUMBER_ID`
  - `TWILIO_ACCOUNT_SID`
  - `TWILIO_AUTH_TOKEN`
  - `TWILIO_FROM_NUMBER`
  - `MANAGER_PHONE_NUMBER`

Security-related recommended keys:

- `DASHBOARD_API_KEY` (protect dashboard endpoints)
- `VAPI_WEBHOOK_SECRET` (protect `/webhook/vapi`)
- `TWILIO_VALIDATE_SIGNATURE=true` (verify Twilio callbacks)

Vapi preflight controls (recommended):

- `VAPI_PREFLIGHT_REQUIRED_FOR_CAMPAIGN=true` (blocks `/start-campaign` on invalid Vapi config)
- `VAPI_REQUIRE_ASSISTANT_SERVER_CONFIG=true` for deployed/tunneled webhook workflows
- `VAPI_REQUIRE_ASSISTANT_SERVER_CONFIG=false` for local call-init testing without webhook deployment

## 3. Install

- Backend: `python -m pip install -r backend/requirements.txt`
- Frontend: `cd frontend && npm install`

## 4. Database Migration

- Run migrations before startup:
  - `cd backend`
  - `alembic -c alembic.ini upgrade head`

## 5. Run

- Backend: `python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`
- Frontend: `cd frontend && npm run dev`

Or use helper script:

- `powershell -ExecutionPolicy Bypass -File scripts/start-demo.ps1`

## 6. Test

- Backend: `python -m pytest backend/tests -q`
- Frontend: `cd frontend && npm run test && npm run build`

## 7. Runtime Diagnostics

- Vapi readiness: `GET /diagnostics/vapi-preflight`
- Typical local-dev expectation (no webhook): `ok=true`, `assistant_has_server=false`
- Typical full lifecycle expectation (with webhook): `ok=true` and assistant/phone/server checks all passing

## Key Robustness Features

- Durable DB-backed campaign queue with retries and job leasing
- Persistent webhook idempotency (`processedwebhookevent`)
- Audit trail (`auditevent`) for campaign/webhook actions
- Optional dashboard API-key protection and endpoint rate limits
- Optional Vapi secret and Twilio signature validation
- Security headers, CORS allow-list, and PII redaction in logs
- Vapi/Twilio retry + circuit breaker protections

## CI

GitHub Actions workflow (`.github/workflows/ci.yml`) runs:

- backend tests
- frontend tests + build
- security checks (`bandit`, `pip-audit`, `npm audit`, `gitleaks`)

## Additional Docs

- `backend/README.md`
- `docs/WEBHOOK-OPERATIONS-RUNBOOK.md`
- `docs/vapi-system-prompt.md`
- `docs/CONTRIBUTING-RUNBOOK.md`
