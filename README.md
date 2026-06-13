# AI Outbound Calling Agent

![CI](https://github.com/N1KH1LT0X1N/Parmar/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![Node 18+](https://img.shields.io/badge/node-18+-brightgreen.svg)

A production-ready open-source template for AI-powered outbound calling. Upload leads via CSV, queue campaigns, and let an AI voice agent qualify prospects via phone. Hot leads are automatically forwarded to a human manager via Twilio.

Built for teams who want a batteries-included starting point with Vapi, FastAPI, React, and robust webhook handling.

## Features

- **CSV lead upload** — Drag-and-drop CSV import with phone normalization
- **Durable campaign queue** — DB-backed queue with retries, job leasing, and concurrency controls
- **AI voice qualification** — Vapi-powered outbound calls with dynamic variables
- **Webhook processing** — Idempotent Vapi + Twilio webhook handlers
- **Hot-lead alerts** — Automatic manager notification via Twilio when interest is high
- **Dashboard** — React + Vite dashboard with live status polling, search, filters, and pagination
- **Security** — Optional API-key auth, rate limits, Vapi secret validation, Twilio signature verification, PII redaction
- **CI/CD** — GitHub Actions with tests, build, and security scanning

## Architecture

```
CSV Upload  -->  Campaign Queue  -->  Vapi Outbound Call
     |                |                       |
     v                v                       v
  SQLite DB      Job Processor      End-of-Call Webhook
                                              |
                                              v
                                    Classifier + Manager Alert
```

## Quick Start

**Option A — Docker (recommended)**

```bash
git clone https://github.com/N1KH1LT0X1N/Parmar.git
cd Parmar
cp .env.example .env
# Fill in VAPI_API_KEY, VAPI_ASSISTANT_ID, VAPI_PHONE_NUMBER_ID,
# TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, MANAGER_PHONE_NUMBER
docker compose up
```

**Option B — Local**

```bash
git clone https://github.com/N1KH1LT0X1N/Parmar.git
cd Parmar
cp .env.example .env
# Edit .env with your credentials
python -m pip install -r backend/requirements.txt
cd backend && alembic -c alembic.ini upgrade head
cd .. && python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
# In another terminal:
cd frontend && npm install && npm run dev
```

**Option C — PowerShell helper**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-demo.ps1
```

## Configuration Reference

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `VAPI_API_KEY` | Vapi API key | — | **Yes** |
| `VAPI_ASSISTANT_ID` | Vapi assistant ID | — | **Yes** |
| `VAPI_PHONE_NUMBER_ID` | Vapi phone number ID | — | **Yes** |
| `TWILIO_ACCOUNT_SID` | Twilio account SID | — | **Yes** |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | — | **Yes** |
| `TWILIO_FROM_NUMBER` | Twilio WhatsApp sender | `whatsapp:+14155238886` | **Yes** |
| `MANAGER_PHONE_NUMBER` | Manager WhatsApp number | — | **Yes** |
| `DASHBOARD_API_KEY` | Protects dashboard endpoints | — | Recommended |
| `VAPI_WEBHOOK_SECRET` | Validates `X-Vapi-Secret` | — | Recommended |
| `TWILIO_VALIDATE_SIGNATURE` | Verify Twilio callbacks | `false` | Recommended |
| `VAPI_PREFLIGHT_REQUIRED_FOR_CAMPAIGN` | Block campaign on invalid config | `true` | No |
| `VAPI_REQUIRE_ASSISTANT_SERVER_CONFIG` | Require assistant webhook URL | `true` | No |
| `DATABASE_URL` | SQLite path | `sqlite:///./database.db` | No |
| `MAX_CONCURRENT_CALLS` | Max parallel calls | `1` | No |
| `MAX_CALL_ATTEMPTS` | Max retries per lead | `3` | No |
| `JOB_POLL_INTERVAL_SECONDS` | Queue poll frequency | `0.5` | No |
| `JOB_LEASE_SECONDS` | Job lock TTL | `60` | No |
| `CORS_ALLOWED_ORIGINS` | Allowed frontend origins | `http://127.0.0.1:5173,http://localhost:5173` | No |
| `LOG_PII_REDACTION_ENABLED` | Redact PII in logs | `true` | No |

See `.env.example` for the full list.

## API Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | — | Health check |
| `GET` | `/ready` | — | Readiness check |
| `POST` | `/upload` | `DASHBOARD_API_KEY` | Upload leads CSV |
| `GET` | `/leads` | `DASHBOARD_API_KEY` | List leads with filters |
| `POST` | `/start-campaign` | `DASHBOARD_API_KEY` | Start calling pending leads |
| `GET` | `/manager-status` | `DASHBOARD_API_KEY` | Twilio connection status |
| `GET` | `/diagnostics/vapi-preflight` | — | Vapi config validation |
| `POST` | `/leads/{lead_id}/do-not-contact` | `DASHBOARD_API_KEY` | Mark lead as DNC |
| `POST` | `/webhook/vapi` | `VAPI_WEBHOOK_SECRET` | End-of-call webhook |
| `POST` | `/webhook/twilio-status` | Signature | Twilio status callback |

## Running Tests

Backend:

```bash
python -m pytest backend/tests -q
```

Frontend:

```bash
cd frontend && npm run test && npm run build
```

## Deployment

**Local development**

- Use `VAPI_REQUIRE_ASSISTANT_SERVER_CONFIG=false` if testing call initiation only (no webhook).
- Set `VAPI_PREFLIGHT_REQUIRED_FOR_CAMPAIGN=true` to validate assistant + phone IDs before dialing.

**Webhook testing with ngrok**

1. Start the backend locally.
2. `ngrok http 8000`
3. Set Vapi assistant server URL to `https://<ngrok-url>/webhook/vapi`.
4. Set `VAPI_REQUIRE_ASSISTANT_SERVER_CONFIG=true`.
5. Confirm `GET /diagnostics/vapi-preflight` returns `ok=true`.

**Production notes**

- Switch from SQLite to PostgreSQL for production workloads.
- Use a secrets manager instead of `.env` files.
- Enable `TWILIO_VALIDATE_SIGNATURE=true` and `VAPI_WEBHOOK_SECRET`.
- Set `DASHBOARD_API_KEY` and consider adding OAuth/SAML for dashboard access.
- Review rate limits and concurrency settings for your call volume.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, branch strategy, and test checklist.

## License

[MIT](LICENSE)
