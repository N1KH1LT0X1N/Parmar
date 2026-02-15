# Design Document: Parmar Properties AI Calling Agent

> ⚠️ **Superseded Document**
>
> This file is retained for history only. Use the finalized consolidated plan instead:
> `docs/2026-02-15-ai-calling-agent-final.md`

## 1. Overview
A web-based demo application that automates outbound sales calls for "Parmar Properties" using AI voice technology. The system uploads a list of leads (CSV), initiates calls using Vapi.ai (powered by ElevenLabs), qualifies leads based on a specific real estate script, and sends hot lead details to a manager via WhatsApp.

## 2. Architecture

### 2.1 Tech Stack
- **Frontend:** React (Vite) + Tailwind CSS
  - Clean, modern dashboard for uploading leads and monitoring call status.
- **Backend:** Python (FastAPI)
  - Handles CSV processing, Vapi.ai webhooks, and Twilio integration.
  - Database: SQLite (simple file-based DB for the demo) to store lead status and call logs.
- **AI Voice Engine:** Vapi.ai
  - **Voice:** ElevenLabs (Indian Accent English).
  - **Model:** `eleven_turbo_v2` for low latency.
- **Telephony & Messaging:** Twilio
  - **Outbound Calls:** Connected via Vapi.ai.
  - **WhatsApp:** Twilio Sandbox API for sending lead summaries.

### 2.2 System Flow
1.  **User Interaction:**
    - User opens the Web UI.
    - Uploads `leads.csv` (Columns: `Name`, `Phone`).
    - Clicks "Start Campaign".
2.  **Orchestration (Backend):**
    - API parses CSV and creates "Lead" entries in the DB.
    - Iterates through leads and triggers Vapi.ai's `POST /call` API.
    - Passes dynamic variables (`{{name}}`, `{{location}}`) to the Vapi assistant.
3.  **The Call (Vapi.ai):**
    - Vapi dials the customer via Twilio.
    - **System Prompt:** "You are [Agent Name] from Parmar Properties..."
    - **Conversation Flow:**
        - Greeting -> Filter (Looking for Mumbai property?) -> Qualification (BHK, Budget, Location) -> Closing.
    - **Interruptibility:** Enabled (user can cut in).
4.  **Post-Call Processing:**
    - Vapi sends a `call.ended` webhook to our backend.
    - Backend analyzes the `analysis.summary` or `transcript`.
    - **Logic:** If `customer_interested` is TRUE:
        - Format a WhatsApp message.
        - Send to Manager via Twilio API.
    - Update UI with status ("Interested", "Not Interested", "Failed").

## 3. Data Structures

### 3.1 Lead Schema
```json
{
  "id": "uuid",
  "name": "Amit Sharma",
  "phone": "+919876543210",
  "status": "pending | calling | completed | failed",
  "interest_level": "high | medium | low | none",
  "summary": "Looking for 2BHK in Juhu, budget 3Cr",
  "call_id": "vapi-call-id"
}
```

### 3.2 CSV Format
```csv
Name,Phone
Amit Sharma,+919876543210
Priya Singh,+919988776655
```

## 4. Key Features for "Wow" Factor
1.  **Real-time Dashboard:** Using WebSocket or Polling to show "Calling..." status live.
2.  **Instant WhatsApp:** The phone buzzes with the lead details seconds after the call ends.
3.  **Indian Context:** The AI will use local terminology (Lakhs/Crores, specific Mumbai locations).

## 5. Setup Requirements
- **Vapi.ai Public Key & Private Key**
- **Twilio Account SID, Auth Token, From Number**
- **ElevenLabs API Key** (managed via Vapi)
- **Python 3.10+**
- **Node.js (for Frontend build)**

## 6. Security Considerations (Demo Scope)
- API Keys stored in `.env`.
- No authentication for the Web UI (local demo only).
- minimal input validation for CSV.
