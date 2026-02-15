# AI Outbound Calling Agent — Blueprint & Implementation Plan

> ⚠️ **Superseded Document**
>
> This file is retained for history only. Use the finalized consolidated plan instead:
> `docs/2026-02-15-ai-calling-agent-final.md`

**Client:** Parmar (Indian Company)
**Platform:** ElevenLabs Conversational AI
**Date:** February 15, 2026

---

## 1. What Are We Building?

An **automated AI outbound calling agent** that:

1. Ingests a CSV/Excel sheet of potential customers (name, phone, any other context)
2. Calls each lead using ElevenLabs Conversational AI + Twilio telephony
3. Follows a structured call script to qualify leads (buyer vs. non-buyer)
4. After each call, extracts structured data (interest level, budget, timeline, objections, etc.)
5. Sends a clean report of **qualified buyers only** to the Head Manager (email/WhatsApp/dashboard)
6. Discards or archives non-buyers

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CONTROL PLANE (Your Backend)                    │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐   │
│  │  CSV/Excel   │───▶│  Campaign    │───▶│  ElevenLabs Batch Call   │   │
│  │  Upload UI   │    │  Manager     │    │  API                     │   │
│  └──────────────┘    └──────────────┘    └───────────┬──────────────┘   │
│                                                      │                  │
│                                                      ▼                  │
│                                          ┌──────────────────────┐       │
│                                          │  ElevenLabs Agent    │       │
│                                          │  (Conversational AI) │       │
│                                          │  + Twilio Phone #    │       │
│                                          └───────────┬──────────┘       │
│                                                      │                  │
│                                          Post-call Webhook              │
│                                                      │                  │
│  ┌──────────────────────────────────────────────────▼──────────────┐   │
│  │                    Webhook Handler (FastAPI)                      │   │
│  │  • Receive transcript + analysis                                 │   │
│  │  • Classify: Buyer ✅ vs Non-Buyer ❌                            │   │
│  │  • Store qualified leads in DB                                   │   │
│  │  • Send summary report to Head Manager                           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐   │
│  │  PostgreSQL  │    │  Email /     │    │  Manager Dashboard       │   │
│  │  Database    │    │  WhatsApp    │    │  (Optional Web UI)       │   │
│  └──────────────┘    └──────────────┘    └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Components Breakdown

### 3.1 Data Ingestion (CSV/Excel Upload)

**What it does:** Takes a spreadsheet of leads and preps it for batch calling.

**CSV Format (Required columns):**

| Column | Required | Example |
|--------|----------|---------|
| `phone_number` | ✅ Yes | `+919876543210` |
| `name` | ✅ Yes | `Rajesh Sharma` |
| `company` | Optional | `Sharma Enterprises` |
| `product_interest` | Optional | `Premium Plan` |
| `city` | Optional | `Mumbai` |
| `previous_interaction` | Optional | `Attended webinar on Jan 10` |
| `language` | Optional | `hi` (Hindi) or `en` (English) |

**Implementation options:**
- **Simple (Demo):** Python script that reads CSV → calls ElevenLabs Batch Calling API
- **Production:** Web UI (React/Next.js) where manager uploads file, previews data, and triggers campaign

### 3.2 ElevenLabs Agent Configuration

This is the brain of the operation. You configure this **entirely within the ElevenLabs platform**.

#### Agent Setup Checklist:
- [ ] Create agent on [ElevenLabs Agents Dashboard](https://elevenlabs.io/app/agents)
- [ ] Write the system prompt (call script — see Section 4)
- [ ] Select voice (Indian English accent or Hindi — ElevenLabs has 5000+ voices)
- [ ] Set language (English, Hindi, or auto-detect)
- [ ] Configure conversation flow (turn-taking, interruption handling)
- [ ] Add dynamic variables (`name`, `company`, `product_interest`, etc.)
- [ ] Configure **Data Collection** rules (see Section 5)
- [ ] Configure **Success Evaluation** criteria
- [ ] Enable **End Call** system tool (so agent can hang up gracefully)
- [ ] Enable **Language Detection** (for Hindi/English switching)

#### Voice Selection Strategy:
- For Indian market: Use a **professional Indian English accent** voice
- Or clone the company's actual sales rep voice (ElevenLabs supports voice cloning)
- Consider having separate Hindi and English voices if needed

### 3.3 Telephony (Twilio Integration)

**Why Twilio?** ElevenLabs has native Twilio integration for outbound calling.

#### Setup Steps:
1. Create Twilio account → Get Indian phone number (+91)
2. Complete India regulatory requirements (TRAI compliance — see Section 8)
3. Import Twilio number into ElevenLabs
4. Link the phone number to your agent

#### India-Specific Considerations:
- **DND Registry:** Must scrub numbers against TRAI's DND list before calling
- **Calling Hours:** Only 9 AM – 9 PM IST (TRAI regulation)
- **Caller ID:** Must display valid Indian number
- **Alternative:** Use [Exotel](https://exotel.com) or [Knowlarity](https://www.knowlarity.com) via SIP trunking if Twilio Indian number is hard to get

### 3.4 Batch Calling (The Campaign Engine)

ElevenLabs has a **built-in Batch Calling feature** — this is exactly what we need.

**How it works:**
1. Upload CSV with `phone_number` column + dynamic variable columns
2. Select your configured agent
3. Select your phone number
4. Schedule or send immediately
5. ElevenLabs handles concurrency, retries, and monitoring

**API approach (for automation):**
```python
from elevenlabs import ElevenLabs

client = ElevenLabs(api_key="your-api-key")

# Create batch call via API
batch = client.batch_calling.create(
    name="Parmar Campaign - Feb 2026",
    agent_id="your-agent-id",
    phone_number_id="your-phone-number-id",
    recipients=[
        {
            "phone_number": "+919876543210",
            "name": "Rajesh Sharma",
            "company": "Sharma Enterprises",
            "product_interest": "Premium Plan"
        },
        # ... more recipients from CSV
    ]
)
```

### 3.5 Post-Call Webhook Handler

After each call, ElevenLabs sends a webhook with the full transcript, analysis, and extracted data.

**What we build:** A FastAPI server that:
1. Receives the webhook
2. Extracts the data collection results (buyer intent, budget, etc.)
3. Classifies the lead
4. Stores qualified leads in database
5. Discards non-buyers (or archives with reason)
6. Triggers notification to manager when batch is complete

```python
from fastapi import FastAPI, Request
from elevenlabs.client import ElevenLabs
import os

app = FastAPI()
elevenlabs = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

@app.post("/webhook/post-call")
async def handle_post_call(request: Request):
    payload = await request.body()
    signature = request.headers.get("elevenlabs-signature")

    event = elevenlabs.webhooks.construct_event(
        payload=payload.decode("utf-8"),
        signature=signature,
        secret=os.getenv("WEBHOOK_SECRET"),
    )

    if event.type == "post_call_transcription":
        data = event.data
        analysis = data.analysis
        
        # Extract collected data
        collected = analysis.data_collection  # dict of your defined fields
        
        is_buyer = collected.get("is_interested_buyer", False)
        
        if is_buyer:
            save_qualified_lead({
                "name": data.conversation_initiation_client_data.get("name"),
                "phone": data.metadata.phone_number,
                "interest_level": collected.get("interest_level"),
                "budget": collected.get("budget"),
                "timeline": collected.get("timeline"),
                "preferred_product": collected.get("preferred_product"),
                "notes": collected.get("additional_notes"),
                "transcript_summary": analysis.transcript_summary,
                "call_duration": data.metadata.call_duration_secs,
            })
        else:
            archive_non_buyer({
                "name": data.conversation_initiation_client_data.get("name"),
                "phone": data.metadata.phone_number,
                "reason": collected.get("rejection_reason"),
                "transcript_summary": analysis.transcript_summary,
            })

    return {"status": "received"}
```

### 3.6 Manager Reporting

**Options (pick one or more):**

| Method | Complexity | Best For |
|--------|-----------|----------|
| **Email Report** | Low | Simple daily/batch summary |
| **WhatsApp Message** | Medium | Real-time alerts per qualified lead |
| **Google Sheets** | Low | Live-updating shared spreadsheet |
| **Web Dashboard** | High | Full campaign analytics & drill-down |

**Recommended for Demo:** Email + Google Sheets (fastest to build, most impressive for Indian business audience)

**Email Report Template:**
```
Subject: 🎯 Campaign Results — Parmar Outbound Campaign (Feb 15, 2026)

Total Calls Made: 150
Connected: 128
Qualified Buyers: 34 (26.5%)
Non-Buyers: 94

TOP QUALIFIED LEADS:
━━━━━━━━━━━━━━━━━━━━
1. Rajesh Sharma | +91-98765-43210 | Budget: ₹5L | Timeline: 2 weeks
   Interest: Premium Plan | Notes: "Very interested, wants demo"
   
2. Priya Patel | +91-87654-32109 | Budget: ₹8L | Timeline: 1 month
   Interest: Enterprise Plan | Notes: "Decision maker, needs proposal"

[Full report attached as CSV]
```

---

## 4. Call Script / System Prompt

This is the most critical piece. The system prompt defines how the agent behaves on every call.

### System Prompt Template:

```
You are a professional sales representative calling on behalf of [COMPANY NAME].
Your name is [AGENT NAME]. You are making an outbound call to a potential customer.

## CALLER INFORMATION (provided as dynamic variables)
- Customer Name: {{name}}
- Company: {{company}}
- Product Interest: {{product_interest}}
- City: {{city}}
- Previous Interaction: {{previous_interaction}}

## YOUR OBJECTIVE
1. Introduce yourself and the company warmly
2. Reference any previous interaction if available
3. Understand the customer's needs and pain points
4. Present the relevant product/service
5. Qualify the lead (budget, authority, need, timeline — BANT)
6. If interested: schedule a follow-up meeting with the sales team
7. If not interested: thank them politely and end the call

## CALL FLOW

### Opening (10-15 seconds)
- Greet warmly: "Hello, am I speaking with {{name}}?"
- Introduce yourself: "This is [AGENT NAME] from [COMPANY NAME]."
- State purpose briefly: "I'm calling regarding [product/service] that might be relevant for you."
- If they previously interacted: "I noticed you [attended our webinar / filled out a form / etc.]"

### Discovery (1-2 minutes)
- Ask about their current situation: "Can I understand what you're currently using for [problem area]?"
- Listen carefully and acknowledge their answers
- Ask about pain points: "What challenges are you facing with your current setup?"

### Pitch (1-2 minutes)
- Present the solution aligned to their pain points
- Keep it concise — 2-3 key benefits maximum
- Use social proof if applicable: "Many companies in [their industry] have seen [specific result]"

### Qualification (BANT)
- **Budget:** "What kind of budget are you working with for this?"
- **Authority:** "Are you the decision-maker for this, or would someone else be involved?"
- **Need:** Confirm the need based on discovery
- **Timeline:** "When are you looking to make a decision on this?"

### Closing
- If INTERESTED: "Great! I'd love to set up a detailed demo with our senior team. Would [day] work for you?"
- If NOT INTERESTED: "I completely understand. Thank you for your time, {{name}}. If anything changes, feel free to reach out."
- If NEEDS TIME: "No problem at all. Can I follow up with you in [timeframe]?"

## RULES
- Be professional but warm — Indian business culture values relationship-building
- NEVER be pushy or aggressive
- If they say they're busy, offer to call back at a convenient time
- If they're clearly not interested after your pitch, gracefully end the call
- Keep total call under 5 minutes unless the customer is engaged
- If asked a question you don't know the answer to, say you'll have a specialist follow up
- Respect "Do Not Disturb" or "Remove my number" requests — note them for compliance
- Speak clearly and at a moderate pace
- If the customer switches to Hindi, respond in Hindi
- Always end with a thank you

## LANGUAGE
- Default: English (Indian English)
- Switch to Hindi if the customer speaks Hindi
- Be culturally respectful — use "ji" suffix when appropriate (e.g., "Rajesh ji")
```

---

## 5. Data Collection Configuration

Configure these in the ElevenLabs Agent's **Analysis** tab:

| Identifier | Type | Extraction Description |
|------------|------|----------------------|
| `is_interested_buyer` | Boolean | "Was the customer interested in purchasing or learning more? True if they showed genuine interest, agreed to a follow-up, or asked detailed questions about pricing. False if they declined, were not interested, or asked to be removed." |
| `interest_level` | String | "Rate the customer's interest: 'hot' (wants to buy now), 'warm' (interested but needs time), 'cold' (not interested), 'dnc' (asked to be removed from list)" |
| `budget` | String | "Extract any budget or spending capacity mentioned by the customer. Include currency (INR/₹). If not mentioned, return 'not disclosed'." |
| `timeline` | String | "When is the customer looking to make a decision? Extract any timeline mentioned (e.g., 'this month', '2 weeks', 'Q2'). If not mentioned, return 'not disclosed'." |
| `decision_maker` | Boolean | "Is the person on the call the decision-maker? True if they confirmed they make the decision, False if they mentioned needing to check with someone else." |
| `preferred_product` | String | "Which specific product or plan did the customer show most interest in?" |
| `follow_up_date` | String | "If a follow-up was scheduled, extract the agreed date/time. If none, return 'none'." |
| `rejection_reason` | String | "If the customer was not interested, what was their primary reason? (e.g., 'using competitor', 'no budget', 'not the right time', 'not relevant')" |
| `customer_sentiment` | String | "Overall sentiment of the customer during the call: 'positive', 'neutral', 'negative'" |
| `key_notes` | String | "Extract 1-2 sentences summarizing the most important takeaway from this conversation for the sales team." |

### Success Evaluation Criteria:

```
The call is successful if ANY of the following are true:
1. The customer agreed to a follow-up meeting or demo
2. The customer expressed genuine interest and provided budget/timeline info
3. The customer requested more information to be sent

The call is unsuccessful if:
1. The customer explicitly declined interest
2. The customer asked to be removed from the call list
3. The call went to voicemail or was not answered
4. The customer hung up before the pitch was delivered
```

---

## 6. Tech Stack Recommendation

### For the Demo (MVP — ship in 3-5 days):

| Component | Technology | Why |
|-----------|-----------|-----|
| AI Agent | ElevenLabs Conversational AI | Core requirement |
| Telephony | Twilio (or SIP trunk to Exotel) | Indian phone numbers |
| Batch Calling | ElevenLabs Batch Calling API | Built-in, no custom code needed |
| Backend | Python + FastAPI | Webhook handler + campaign trigger |
| Database | SQLite (demo) → PostgreSQL (prod) | Store results |
| Reporting | Google Sheets API + Email (SendGrid) | Manager-friendly |
| Hosting | Railway / Render / AWS Lightsail | Quick deploy with HTTPS |

### For Production (Phase 2):

| Component | Technology | Why |
|-----------|-----------|-----|
| Frontend | Next.js dashboard | Campaign management + analytics |
| Database | PostgreSQL + Redis | Scale + caching |
| File Storage | S3 | Call recordings |
| Auth | Clerk / NextAuth | Multi-user access |
| Monitoring | Sentry + Datadog | Error tracking |
| Scheduling | Celery / APScheduler | Timed campaigns |

---

## 7. Implementation Plan (Demo MVP)

### Day 1: Agent Setup
- [ ] Create ElevenLabs account (Scale plan for phone features)
- [ ] Set up Twilio account + get Indian phone number
- [ ] Create the AI agent with system prompt
- [ ] Select and test voice (Indian English)
- [ ] Configure dynamic variables
- [ ] Test agent with widget (web chat first)

### Day 2: Telephony + Batch Calling
- [ ] Import Twilio number into ElevenLabs
- [ ] Link phone number to agent
- [ ] Configure data collection rules (10 fields above)
- [ ] Configure success evaluation
- [ ] Test with a single outbound call to your own phone
- [ ] Fix prompt based on real call experience

### Day 3: Backend + Webhook
- [ ] Set up FastAPI project
- [ ] Set up ngrok/tunnel for webhook development
- [ ] Implement webhook handler
- [ ] Implement lead classification logic
- [ ] Set up SQLite database for results
- [ ] Test end-to-end: trigger call → receive webhook → classify lead

### Day 4: Reporting + Polish
- [ ] Build email report generation (SendGrid / SMTP)
- [ ] Build Google Sheets integration (optional)
- [ ] Create CSV upload script that triggers batch calls
- [ ] Test full pipeline with 5-10 test calls
- [ ] Iterate on prompt for natural conversation flow

### Day 5: Demo Prep
- [ ] Deploy backend to Railway/Render
- [ ] Prepare sample CSV with test data
- [ ] Record one great demo call
- [ ] Prepare presentation deck
- [ ] Rehearse the live demo flow

---

## 8. India Regulatory Compliance (TRAI)

**Critical for the real deployment. Demo can skip some of these.**

| Requirement | Details | How to Handle |
|-------------|---------|---------------|
| **DND Scrubbing** | Cannot call numbers on National DND Registry | Integrate with TRAI DND API to scrub list before calling |
| **Calling Hours** | 9:00 AM – 9:00 PM IST only | Schedule batch calls within this window |
| **Consent** | Should have prior consent or existing relationship | Ensure CSV only contains opted-in leads |
| **Opt-Out** | Must honor "remove my number" requests | Agent trained to note this; webhook handler flags DNC |
| **Caller ID** | Must show valid registered number | Use registered Twilio/Exotel Indian number |
| **AI Disclosure** | Emerging regulation — may need to disclose AI caller | Add to opening: "This call may be AI-assisted" |
| **Recording Consent** | Should inform about recording | Agent mentions: "This call may be recorded for quality" |

---

## 9. Cost Estimation

### ElevenLabs Pricing (Estimated):
| Item | Cost |
|------|------|
| Scale Plan | ~$99/month |
| Conversational AI minutes | ~$0.07-0.10/min (depends on plan) |
| Per 5-min call | ~$0.35-0.50 |
| 1000 calls/month (5 min avg) | ~$350-500/month |

### Twilio Pricing (India):
| Item | Cost |
|------|------|
| Indian phone number | ~₹800/month (~$10) |
| Outbound call per minute (India) | ~₹0.50-1.50/min (~$0.01-0.02) |
| 1000 calls × 5 min | ~₹5,000 (~$60) |

### Total Monthly (1000 calls):
**Estimated: $450-600/month** (~₹38,000-50,000)

This is **dramatically cheaper** than a human call center agent (₹20,000-30,000/month salary for ONE agent who can make ~50-80 calls/day max).

---

## 10. Demo Strategy — How to Impress

### The "Wow" Moments:

1. **Live Upload:** Upload a CSV → calls start within 30 seconds
2. **Live Call:** Have a volunteer's phone ring during the demo, put it on speaker — everyone hears the AI agent have a natural conversation
3. **Real-Time Dashboard:** Show calls completing and results flowing into Google Sheets in real-time
4. **Multilingual:** Show the agent seamlessly switching from English to Hindi mid-conversation
5. **Instant Report:** Within minutes of batch completion, show the email report landing in the manager's inbox
6. **Numbers:** "100 calls that would take your team 2 days — done in 2 hours at 1/10th the cost"

### Demo Script:

```
1. OPEN with the problem: "Your sales team spends 70% of their time calling 
   leads that go nowhere. What if an AI could do the filtering for you?"

2. SHOW the CSV upload: "Here's your lead list — 50 potential customers."
   → Upload, click "Start Campaign"

3. LIVE CALL: Have a planted volunteer answer → showcase natural conversation

4. SHOW RESULTS: Switch to Google Sheet → qualified leads appearing in real-time

5. SHOW REPORT: Open email → clean summary for the Head Manager
   "Only the buyers. No noise. No wasted time."

6. COST COMPARISON: 
   "Human agent: 50 calls/day, ₹25,000/month salary
    AI agent: 500 calls/day, ₹5,000/month cost
    10x capacity at 1/5th the cost."

7. CLOSE: "And this is just day one. The AI gets better with every call."
```

---

## 11. Project Structure (Code)

```
parmar-call-agent/
├── app/
│   ├── main.py              # FastAPI app — webhook handler + API
│   ├── config.py             # Environment variables and settings
│   ├── models.py             # Pydantic models for leads, calls, etc.
│   ├── services/
│   │   ├── elevenlabs.py     # ElevenLabs API wrapper (batch calls)
│   │   ├── csv_parser.py     # CSV/Excel ingestion and validation
│   │   ├── lead_classifier.py # Buyer vs Non-buyer classification
│   │   ├── reporter.py       # Email/WhatsApp/Sheets reporting
│   │   └── database.py       # Database operations
│   └── templates/
│       └── email_report.html # Email report template
├── data/
│   ├── sample_leads.csv      # Sample CSV for demo
│   └── output/               # Generated reports
├── scripts/
│   ├── run_campaign.py       # CLI script to trigger a campaign
│   └── setup_agent.py        # Helper to configure ElevenLabs agent
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
├── Dockerfile                # For deployment
└── README.md                 # Setup instructions
```

---

## 12. Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Twilio Indian number delays | Can't demo calls | Use SIP trunk to Exotel as backup, or demo with US/UK number |
| AI sounds robotic | Bad demo impression | Spend time tuning voice + prompt; test 20+ calls before demo |
| Hindi language quality | Poor Hindi conversations | Test Hindi extensively; consider English-only for Phase 1 |
| Call drops / latency | Unreliable experience | Test network conditions; have backup recorded demo |
| TRAI compliance | Legal issues in production | Run demo with team's own numbers; handle compliance before production |
| ElevenLabs outage | Demo failure | Have a recorded backup video of a perfect call |

---

## 13. Open Questions to Resolve

1. **What does Parmar's company sell?** (Need this to write an accurate call script)
2. **What's the call script from the image?** (Need to incorporate their specific instructions)
3. **Hindi or English or both?** (Affects voice selection and prompt)
4. **How many leads per campaign?** (Affects pricing and concurrency)
5. **What CRM does the manager use?** (Determines reporting integration)
6. **Do they have existing Twilio/telephony?** (Could simplify setup)
7. **Budget for the demo?** (ElevenLabs Scale plan needed for phone features)
8. **Timeline for the demo?** (Affects how much we build)

---

## 14. Next Steps

- [ ] Get answers to open questions above
- [ ] Get the call script/instructions from the image transcribed
- [ ] Set up ElevenLabs + Twilio accounts
- [ ] Build and test the agent with the specific script
- [ ] Build the backend webhook handler
- [ ] Run 20+ test calls and iterate on the prompt
- [ ] Prepare demo environment
- [ ] Rehearse and deliver

---

*This is a living document. Update as decisions are made.*
