# Backend (Parmar AI Calling Agent)

FastAPI backend for:
- lead uploads and campaign orchestration
- outbound call initiation via Vapi
- webhook processing (Vapi + Twilio)
- hot-lead manager notifications via Twilio

## Setup

1. Install dependencies:
- `python -m pip install -r requirements.txt`

2. Configure environment:
- Use repo-root `.env` (see `.env.example`)

3. Run migrations:
- `alembic -c alembic.ini upgrade head`

4. Start API:
- `python -m uvicorn app.main:app --reload`

## Important Environment Flags

- `DASHBOARD_API_KEY`: protects dashboard endpoints (`/upload`, `/leads`, `/start-campaign`, `/manager-status`, `/leads/{id}/do-not-contact`)
- `VAPI_WEBHOOK_SECRET`: requires `X-Vapi-Secret` on `/webhook/vapi`
- `TWILIO_VALIDATE_SIGNATURE=true`: validates `X-Twilio-Signature` on `/webhook/twilio-status`
- `ENABLE_TEST_ENDPOINTS=true`: enables `/test/*` routes (disabled by default)

Reliability tuning:
- `MAX_CONCURRENT_CALLS`, `MAX_CALL_ATTEMPTS`, `JOB_POLL_INTERVAL_SECONDS`, `JOB_LEASE_SECONDS`
- `VAPI_MAX_RETRIES`, `VAPI_CIRCUIT_*`
- `TWILIO_MAX_RETRIES`, `TWILIO_CIRCUIT_*`
- `WEBHOOK_DEDUPE_TTL_SECONDS`, `*_RETENTION_DAYS`

## Endpoints

Core:
- `GET /health`
- `GET /ready`
- `POST /upload`
- `GET /leads`
- `POST /start-campaign`
- `GET /manager-status`
- `POST /leads/{lead_id}/do-not-contact`

Webhooks:
- `POST /webhook/vapi`
- `POST /webhook/twilio-status`

Optional test-only (requires `ENABLE_TEST_ENDPOINTS=true`):
- `POST /test/mark-call-completed/{call_id}`
- `POST /test/lead/{lead_id}/simulate-completion`

## Testing
- `python -m pytest tests -q`
