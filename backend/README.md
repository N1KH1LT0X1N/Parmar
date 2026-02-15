# Phase 1 Backend (Parmar AI Calling Agent)

## Run

- Create/activate Python environment.
- Install dependencies: `python -m pip install -r backend/requirements.txt`
- Copy `.env.example` to `.env` and fill keys.
- Optional env mode: `ENV_VALIDATION_MODE=warn` (default) or `strict`.
- Start API: `python -m uvicorn app.main:app --app-dir backend --reload`

## One-command Demo Launch

- From repo root: `powershell -ExecutionPolicy Bypass -File scripts/start-demo.ps1`
- Strict mode: `powershell -ExecutionPolicy Bypass -File scripts/start-demo.ps1 -ValidationMode strict`
- Install deps before launch: `powershell -ExecutionPolicy Bypass -File scripts/start-demo.ps1 -InstallDeps`
- Stop demo services: `powershell -ExecutionPolicy Bypass -File scripts/stop-demo.ps1`

## Test

- `python -m pytest backend/tests -q`

## Implemented Endpoints

- `POST /upload`
- `GET /leads`
- `POST /start-campaign`
- `GET /manager-status`
- `POST /webhook/vapi`
