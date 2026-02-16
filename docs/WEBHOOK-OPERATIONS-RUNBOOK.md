# Webhook Operations Runbook

## Scope

Operational checks for:
- `POST /webhook/vapi`
- `POST /webhook/twilio-status`

## Security Controls

- Optional Vapi shared secret: `VAPI_WEBHOOK_SECRET` + `X-Vapi-Secret` header.
- Optional Twilio signature validation: `TWILIO_VALIDATE_SIGNATURE=true`.
- Persistent webhook dedupe ledger table: `processedwebhookevent`.
- Deduplication freshness window: `WEBHOOK_DEDUPE_TTL_SECONDS`.
- Audit events table: `auditevent`.

## Incident: High Webhook Error Rate

1. Check API logs for `Invalid Vapi webhook secret` and `Invalid Twilio signature`.
2. Confirm provider-side webhook credentials match local `.env` values.
3. Verify service health at `GET /health`.
4. Confirm database is reachable and writable.

## Incident: Missing Call Updates

1. Confirm Vapi is sending events to `/webhook/vapi`.
2. Verify `X-Vapi-Secret` is configured correctly if secret validation is enabled.
3. Check whether events are non-terminal (`status` returns `ignored`).
4. Confirm call IDs in payload match `Lead.call_id` values.

## Incident: Duplicate Webhook Events

1. Confirm duplicate responses (`status=duplicate_ignored`) are present in logs.
2. Verify `WEBHOOK_DEDUPE_TTL_SECONDS` is not set too low.
3. Inspect `processedwebhookevent` for repeated `provider + event_key` rows and statuses.
4. Review provider retry behavior and ensure 200 responses are returned for processed events.

## Post-Incident

1. Document root cause and exact remediation.
2. Add or update automated tests for the failure mode.
3. Review whether webhook secret rotation is needed.
4. Confirm retention jobs are pruning old webhook/audit records (`*_RETENTION_DAYS`).
