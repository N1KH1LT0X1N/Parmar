# Backend (Parmar AI Calling Agent)

FastAPI backend for:

- lead uploads and campaign orchestration
- outbound call initiation via Vapi
- webhook processing (Vapi + Twilio)
- hot-lead manager notifications via Twilio

## Setup

1. Install dependencies:

- `python -m pip install -r requirements.txt`

1. Configure environment:

- Use repo-root `.env` (see `.env.example`)
- Backend settings read only repo-root `.env` (not `backend/.env`) to avoid environment drift

1. Run migrations:

- `alembic -c alembic.ini upgrade head`

1. Start API:

- `python -m uvicorn app.main:app --reload`

## Important Environment Flags

- `DASHBOARD_API_KEY`: protects dashboard endpoints (`/upload`, `/leads`, `/start-campaign`, `/manager-status`, `/leads/{id}/do-not-contact`)
- `VAPI_WEBHOOK_SECRET`: requires `X-Vapi-Secret` on `/webhook/vapi`
- `VAPI_PREFLIGHT_REQUIRED_FOR_CAMPAIGN=true`: blocks `/start-campaign` when assistant/phone-number/webhook prechecks fail
- `VAPI_REQUIRE_ASSISTANT_SERVER_CONFIG=true`: requires assistant-level server URL configuration for end-of-call webhooks
- `VAPI_EXPECTED_SERVER_URL`: optional exact webhook URL check during preflight
- `VAPI_VERIFY_ASSISTANT_BEFORE_CALL=true`: preflight fetches assistant config before dialing
- `VAPI_EXPECTED_ASSISTANT_NAME`: optional exact-name guard to catch wrong `VAPI_ASSISTANT_ID`
- `VAPI_EXPECTED_PROMPT_CONTAINS`: optional snippet guard to detect prompt drift/mismatch
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
- `GET /diagnostics/vapi-preflight`
- `POST /leads/{lead_id}/do-not-contact`

Webhooks:

- `POST /webhook/vapi`
- `POST /webhook/twilio-status`

Optional test-only (requires `ENABLE_TEST_ENDPOINTS=true`):

- `POST /test/mark-call-completed/{call_id}`
- `POST /test/lead/{lead_id}/simulate-completion`

## Testing

- `python -m pytest tests -q`
