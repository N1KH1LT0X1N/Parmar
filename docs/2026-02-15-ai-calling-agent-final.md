# Final Consolidated Plan: Parmar Properties AI Calling Agent

**Date:** February 15, 2026  
**Prepared for:** Parmar Properties (India)  
**Objective:** Build a strong working demo that uploads leads, makes outbound AI calls, qualifies buyers, and notifies the manager with only high-intent leads.

---

## 1) Executive Summary

This final plan merges and reconciles the three source documents into one implementation blueprint.

### Final Architecture Decision (for demo)
- **Call orchestration:** Vapi.ai
- **Voice:** ElevenLabs voice through Vapi
- **Telephony + WhatsApp notifications:** Twilio
- **Backend:** FastAPI + SQLite (SQLModel)
- **Frontend:** React (Vite) + custom CSS

### Why this decision
- Two source docs are already Vapi-first and contain actionable implementation details.
- Vapi simplifies live call orchestration and webhook handling for a fast demo.
- ElevenLabs quality is preserved through Vapi voice provider integration.
- Twilio WhatsApp gives immediate manager-facing “wow” feedback.

### Validation notes (docs-checked)
- Vapi outbound flow uses `POST /call` with `assistantId`, `phoneNumberId`, and `customer.number`.
- Vapi server webhook includes `message.type = end-of-call-report` and `message.call.id` for call mapping.
- Twilio WhatsApp Sandbox is demo-only and requires each recipient to join the sandbox first.

---

## 2) Reconciliation of the 3 Documents

## 2.1 What was aligned
- CSV upload → lead ingestion → outbound calls → post-call analysis → manager notifications.
- Indian-market positioning (Mumbai real estate context, INR terms, localities).
- FastAPI backend + React dashboard + SQLite for demo speed.

## 2.2 Conflicts resolved

| Conflict | Source Difference | Final Decision |
|---|---|---|
| Primary call platform | ElevenLabs direct batch vs Vapi-first | **Vapi-first for demo** |
| Notification strategy | Email/Sheets vs WhatsApp | **WhatsApp primary**, email optional later |
| Trigger mode | Native batch call vs queued API calls | **Backend queue with throttling** |
| Qualification logic | Rich data collection vs keyword-only summary | **Hybrid: structured fields + fallback summary** |

## 2.3 Fallback option
If Vapi path is blocked during demo prep, fallback to **ElevenLabs native Batch Calling** with the same CSV and webhook post-processing approach.

---

## 3) Final System Scope (MVP Demo)

### In scope
1. Upload CSV (`Name`, `Phone` required)
2. View leads in dashboard
3. Start campaign
4. Place outbound calls via Vapi
5. Receive post-call webhook
6. Classify lead (`high`, `medium`, `low`, `none` + status)
7. Send WhatsApp alert to manager for hot leads
8. Live status updates in UI (polling every 2s is acceptable)

### Out of scope (phase 2)
- Full CRM sync
- Multi-user auth/roles
- Advanced retry scheduler
- Production-grade analytics and BI dashboards

---

## 4) End-to-End Flow

1. User uploads CSV in web app.
2. Backend validates and stores leads in SQLite.
3. User clicks **Start Campaign**.
4. Backend queues leads and starts calls with controlled concurrency.
5. Backend calls Vapi `POST /call` using `assistantId`, `phoneNumberId`, and `customer.number`.
6. Vapi executes voice call via Twilio.
7. Vapi sends end-of-call webhook (`end-of-call-report`).
8. Backend maps webhook to lead by `message.call.id`, updates status/summary/interest.
9. If lead is qualified (hot), backend sends WhatsApp summary to manager.
10. Frontend reflects latest state from `/leads` API.

---

## 5) Data Contracts

## 5.1 CSV input format
```csv
Name,Phone,Location,BudgetRange,BHKPreference
Amit Sharma,+919876543210,Juhu,2.5-3Cr,2BHK
Priya Singh,+919988776655,Bandra,3-4Cr,3BHK
```

### Required columns
- `Name`
- `Phone` (E.164 format preferred, e.g., `+91...`)

### Optional columns (recommended)
- `Location`
- `BudgetRange`
- `BHKPreference`

## 5.2 Lead schema (backend)
```json
{
  "id": 1,
  "name": "Amit Sharma",
  "phone": "+919876543210",
  "status": "pending|queued|calling|completed|failed|voicemail",
  "interest_level": "high|medium|low|none",
  "summary": "Interested in 2BHK Juhu, budget up to 3Cr",
  "call_id": "vapi-call-id",
  "created_at": "2026-02-15T10:30:00Z"
}
```

---

## 6) Calling Script (Final Draft for Parmar Properties)

Use this as the assistant system prompt template in Vapi:

```text
You are a polite, professional outbound sales caller for Parmar Properties.
You are calling potential buyers for residential properties in Mumbai.

Goals:
1) Confirm if customer is currently looking for property in Mumbai.
2) If yes, capture: preferred locality, BHK requirement, budget range, purchase timeline.
3) Qualify interest level and ask permission for a follow-up by a human relationship manager.
4) Keep call concise (2-4 minutes unless customer is engaged).

Style:
- Use Indian business tone, respectful and clear.
- Use INR terms naturally: lakhs/crores.
- Never be pushy.
- If user is busy, ask for better callback slot.
- If user asks to stop calls, acknowledge and mark as do-not-contact.

Opening:
- "Hello, am I speaking with {{name}}?"
- "This is [Agent Name] from Parmar Properties. We help buyers with verified Mumbai listings."
- "Is this a good time for a quick 2-minute call?"

Qualification questions:
- "Are you currently looking to buy property in Mumbai?"
- "Which areas are you considering?"
- "What configuration are you looking for (1/2/3 BHK)?"
- "What budget range are you planning for?"
- "By when are you planning to finalize?"

Close:
- If interested: Ask consent for a follow-up from sales manager.
- If not interested: Thank them politely and end call.
```

---

## 7) Lead Qualification Rules (Final)

### Hot lead (notify manager on WhatsApp)
- Customer confirms active buying intent **and**
- At least two of these are captured:
  - locality preference
  - BHK preference
  - budget
  - timeline

### Medium lead
- Interested but vague / wants callback later.

### Low lead
- Passive interest, no clear requirement or timeline.

### None / DNC
- Not interested, wrong number, or asks to stop calls.

---

## 8) API Endpoints (MVP)

- `POST /upload` → parse CSV and insert leads
- `GET /leads` → list current campaign leads
- `POST /start-campaign` → queue pending leads
- `GET /manager-status` → WhatsApp sandbox info for demo instructions
- `POST /webhook/vapi` → receive end-of-call payload and update lead

### External API contracts used by backend
- **Vapi outbound call:** `POST /call`
  - Required payload fields: `assistantId`, `phoneNumberId`, `customer.number`
- **Vapi webhook event:** `message.type = end-of-call-report`
  - Required fields read: `message.call.id`, `message.endedReason`, `message.artifact.transcript` (or summary fields)

---

## 9) Environment Variables

```env
VAPI_API_KEY=
VAPI_ASSISTANT_ID=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=whatsapp:+14155238886
MANAGER_PHONE_NUMBER=whatsapp:+91XXXXXXXXXX
MAX_CONCURRENT_CALLS=1
```

---

## 10) Demo Build Plan (5 Days)

### Day 1
- Backend skeleton, DB models, CSV upload API
- Frontend scaffold with upload table view

### Day 2
- Vapi call initiation + queue processing
- Lead status transitions wired to UI

### Day 3
- Webhook ingestion + lead classification
- Twilio WhatsApp notifications for hot leads

### Day 4
- Prompt tuning with 10+ real test calls
- Improve summary formatting and status badges

### Day 5
- Full end-to-end rehearsal
- Backup recorded demo in case of network/provider issues

---

## 11) Compliance Notes (India)

Before production rollout (not optional):
- Call only consented leads
- Respect DND / opt-out immediately
- Restrict calling windows to local regulations
- Use valid caller identity and approved telephony setup
- Add disclosure if your legal team requires AI-assistance statement

### Demo messaging caveat
- Twilio WhatsApp Sandbox may restrict business-initiated free-form messaging unless recipient is in the active customer-service window.
- For predictable demos, have the manager number join sandbox in advance and keep a template-message fallback ready.

---

## 12) Known Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Twilio sandbox issues on demo day | Verify sandbox join in advance + keep manager test number ready |
| Poor recognition of Mumbai localities | Add vocabulary hints and tune script wording |
| Webhook mismatch | Log raw payloads and keep tolerant parser |
| Call quality fluctuations | Keep backup pre-recorded successful demo |

---

## 13) Immediate Next Actions

1. Freeze assistant prompt and variables.
2. Build backend APIs and queue first.
3. Connect Vapi + Twilio and run 3 internal test calls.
4. Add webhook classification + WhatsApp trigger.
5. Run 20-call dry run with mixed lead quality.

---

## 14) Final Note

This consolidated document is now the **single source of truth** for implementation.  
Use it instead of the earlier three docs to avoid stack confusion.
