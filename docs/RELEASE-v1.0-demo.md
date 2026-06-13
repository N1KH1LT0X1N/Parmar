# Release Notes — v1.0-demo

**Date:** February 15, 2026

## Summary

First complete demo release of the AI Outbound Calling Agent.

This release includes:

- Phase 1 backend (FastAPI + queue + webhook + lead classification)
- Phase 2 frontend dashboard (upload, start campaign, live status polling)
- Vapi outbound call integration and Twilio WhatsApp integration paths
- Test coverage and runbooks for team handoff

## Included Components

### Backend

- Lead ingestion API (`/upload`)
- Lead listing API (`/leads`)
- Campaign queue trigger (`/start-campaign`)
- Vapi webhook receiver (`/webhook/vapi`)
- Manager status endpoint (`/manager-status`)

### Frontend

- Campaign dashboard UI
- CSV upload and start campaign actions
- Live lead status table
- Trial mode warning banner

### Scripts

- `scripts/start-demo.ps1`
- `scripts/stop-demo.ps1`
- Vapi debug scripts for troubleshooting

## Verification Status

- Backend tests: pass
- Frontend tests: pass
- Frontend production build: pass
- Runtime smoke checks: pass

## Operational Notes

- Twilio trial accounts may inject a keypress prompt before call connection.
- Real call completion depends on provider webhook timing.
- Use `.env.example` as baseline and keep secrets out of git.

## Recommended Next Steps

- Upgrade Twilio from trial for smoother production-like demos.
- Add CRM destination integration for finalized lead handoff.
- Add role-based auth for dashboard access in production phase.
