# Contributing to AI Outbound Calling Agent

Thank you for considering contributing to this project!

## Setup

1. Clone the repository.
2. Copy `.env.example` to `.env` and fill in your provider credentials (Vapi / Twilio).
3. Install dependencies:
   - Backend: `python -m pip install -r backend/requirements.txt`
   - Frontend: `cd frontend && npm install`
4. Run database migrations: `cd backend && alembic -c alembic.ini upgrade head`

## Start Services

- Recommended: `powershell -ExecutionPolicy Bypass -File scripts/start-demo.ps1`
- Strict env validation: `... -ValidationMode strict`
- Or with Docker: `docker compose up`

## Branch and Commit Strategy

- Create a feature branch from the latest default branch.
- Keep PR scope small (backend or frontend, not both when possible).
- Include test evidence in the PR description.

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

- Keep API responses backward compatible where possible.
- Do not hardcode secrets or credentials.
- Use environment-driven config only.
- CSV phone values are normalized to E.164 where possible.
- Webhook processing is idempotent for duplicate end-of-call payloads.
- Preserve existing lead statuses: `pending`, `queued`, `calling`, `completed`, `failed`, `voicemail`.

## Linting and Formatting

This project uses `ruff` for Python linting and formatting.

```bash
# Check all files
ruff check backend

# Format all files
ruff format backend
```

Pre-commit hooks are configured in `.pre-commit-config.yaml`. Install them with:

```bash
pre-commit install
```

## Reporting Bugs

Please use the [bug report issue template](https://github.com/N1KH1LT0X1N/Parmar/issues/new/choose) and include:

- Steps to reproduce.
- Expected vs actual behavior.
- Environment (OS, Python version, Node version).

## Security Issues

See [SECURITY.md](SECURITY.md) for how to report vulnerabilities responsibly.
