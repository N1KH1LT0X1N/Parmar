# Parmar AI Calling Agent

Production-style demo for outbound lead qualification using:
- **Backend:** FastAPI + SQLModel (SQLite for demo)
- **Frontend:** React + Vite
- **Calling:** Vapi (with ElevenLabs voice)
- **Messaging:** Twilio (WhatsApp sandbox/number)

## Project Structure

- `backend/` — APIs, queueing, webhook processing, qualification logic
- `frontend/` — dashboard for upload/start/monitor
- `docs/` — architecture, implementation notes, prompts, handoff docs
- `scripts/` — helper scripts for starting/stopping/debugging demo

## Quick Start

## 1) Prerequisites

- Python 3.10+
- Node.js 18+
- Vapi account + assistant + phone number
- Twilio account (trial/paid)

## 2) Environment

Create `.env` in repo root using `.env.example` as base.

Required keys:
- `VAPI_API_KEY` or `VAPI_PRIVATE_KEY`
- `VAPI_ASSISTANT_ID`
- `VAPI_PHONE_NUMBER_ID`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`
- `MANAGER_PHONE_NUMBER`

Optional:
- `ENV_VALIDATION_MODE=warn` (or `strict`)

## 3) Install

Backend:
- `python -m pip install -r backend/requirements.txt`

Frontend:
- `cd frontend && npm install`

## 4) Run (one command)

- `powershell -ExecutionPolicy Bypass -File scripts/start-demo.ps1`

Manual run:
- Backend: `python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`
- Frontend: `cd frontend && npm run dev`

## 5) Test

- Backend: `python -m pytest backend/tests -q`
- Frontend: `cd frontend && npm run test && npm run build`

## Trial-mode note

On Twilio trial accounts, recipients may hear:
"This is a trial account, press any number..."

This is expected trial behavior. Upgrade Twilio to remove it.

## Core Docs

- `docs/2026-02-15-ai-calling-agent-final.md` — final architecture and plan
- `docs/2026-02-15-implementation-status.md` — implementation/test status
- `docs/vapi-system-prompt.md` — copy-paste Vapi prompt/settings
