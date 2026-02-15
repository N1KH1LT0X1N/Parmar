# AI Calling Agent Implementation Plan (Refined)

> ⚠️ **Superseded Document**
>
> This file is retained for history only. Use the finalized consolidated plan instead:
> `docs/2026-02-15-ai-calling-agent-final.md`

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a "Parmar Properties" AI calling agent demo with a React frontend, FastAPI backend, Vapi.ai voice integration (with Indian context optimizations), and Twilio WhatsApp notifications (with connection status).

**Architecture:**
- **Frontend:** React + Tailwind (Vite)
- **Backend:** FastAPI (Python) with `asyncio` Queue for throttling
- **Database:** SQLite (SQLModel)
- **Voice AI:** Vapi.ai (ElevenLabs Turbo v2.5 + Vocabulary Injection)
- **Notifications:** Twilio Sandbox (with status check)

**Tech Stack:** Python 3.10+, React 18, FastAPI, SQLModel, HTTPX, Twilio Python Helper Library.

---

### Task 1: Environment Setup & Project Structure

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/main.py`
- Create: `frontend/package.json` (via init)
- Create: `.env`

**Step 1: Create directory structure**
```bash
mkdir -p backend frontend
```

**Step 2: Setup Python Backend Environment**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
```

**Step 3: Create requirements.txt**
```text
fastapi
uvicorn
python-multipart
sqlmodel
httpx
twilio
python-dotenv
pandas
aiofiles
```

**Step 4: Install Python dependencies**
```bash
pip install -r requirements.txt
```

**Step 5: Setup React Frontend**
```bash
cd ../frontend
npm create vite@latest . -- --template react
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install axios lucide-react
```

**Step 6: Configure Tailwind**
Modify `frontend/tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

Add directives to `frontend/src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**Step 7: Create .env file (Template)**
Create `.env` in root:
```text
VAPI_API_KEY=your_vapi_key
VAPI_ASSISTANT_ID=your_assistant_id
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_FROM_NUMBER=whatsapp:+14155238886
MANAGER_PHONE_NUMBER=whatsapp:+919876543210
```

### Task 2: Backend - Database & Models

**Files:**
- Create: `backend/models.py`
- Create: `backend/database.py`

**Step 1: Define SQLModel Models**
Create `backend/models.py`:
```python
from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime

class Lead(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str
    status: str = Field(default="pending")  # pending, queued, calling, completed, failed, voicemail
    interest_level: Optional[str] = None
    summary: Optional[str] = None
    call_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

**Step 2: Setup Database Connection**
Create `backend/database.py`:
```python
from sqlmodel import SQLModel, create_engine, Session

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
```

### Task 3: Backend - Queue & Call Logic (Throttled)

**Files:**
- Modify: `backend/main.py`

**Step 1: Basic FastAPI App & Queue**
In `backend/main.py`:
```python
from fastapi import FastAPI, UploadFile, File, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from database import create_db_and_tables, get_session
from models import Lead
import pandas as pd
import io
import httpx
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Simple in-memory queue for demo throttling
call_queue = asyncio.Queue()
active_calls = 0
MAX_CONCURRENT_CALLS = 1

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    create_db_and_tables()
    asyncio.create_task(process_call_queue())

async def process_call_queue():
    global active_calls
    while True:
        if active_calls < MAX_CONCURRENT_CALLS and not call_queue.empty():
            lead_id = await call_queue.get()
            active_calls += 1
            # We need a fresh session here since this runs in background loop
            with Session(engine) as session:
                await initiate_vapi_call(lead_id, session)
            call_queue.task_done()
        await asyncio.sleep(1) # Check queue every second
```

**Step 2: Vapi Call Function with Vocabulary Injection**
Add to `backend/main.py`:
```python
VAPI_API_URL = "https://api.vapi.ai/call/phone"
VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")

async def initiate_vapi_call(lead_id: int, session: Session):
    global active_calls
    lead = session.get(Lead, lead_id)
    if not lead:
        active_calls -= 1
        return

    headers = {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json"
    }

    # Vocabulary injection for Indian localities
    mumbai_localities = ["Juhu", "Bandra", "Andheri", "Worli", "Dadar", "Powai", "Goregaon", "Malad", "Colaba"]

    payload = {
        "phoneNumber": lead.phone,
        "assistantId": VAPI_ASSISTANT_ID,
        "customer": {
            "number": lead.phone,
            "name": lead.name
        },
        "assistantOverrides": {
            "variableValues": {
                "name": lead.name
            },
            "transcriber": {
                "provider": "deepgram",
                "model": "nova-2",
                "keywords": mumbai_localities # Hinting for better recognition
            },
            "voice": {
                "provider": "11labs",
                "voiceId": "eleven_turbo_v2_5", # Low latency model
            },
            "analysis": {
                 "summaryPrompt": "Summarize the call focusing on budget, BHK preference, and location interest."
            }
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(VAPI_API_URL, json=payload, headers=headers)

        if response.status_code == 201:
            data = response.json()
            lead.status = "calling"
            lead.call_id = data.get("id")
            session.add(lead)
            session.commit()
        else:
            lead.status = "failed"
            session.add(lead)
            session.commit()
            active_calls -= 1 # Only decrement if call failed to start
    except Exception as e:
        print(f"Error starting call: {e}")
        lead.status = "failed"
        session.add(lead)
        session.commit()
        active_calls -= 1
```

**Step 3: Endpoints for Upload & Queueing**
Add to `backend/main.py`:
```python
@app.post("/upload")
async def upload_leads(file: UploadFile = File(...), session: Session = Depends(get_session)):
    contents = await file.read()
    # Basic CSV parsing
    try:
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
    except:
        return {"error": "Invalid CSV format"}

    leads = []
    for _, row in df.iterrows():
        # Basic normalization could happen here
        lead = Lead(name=str(row.get('Name', '')), phone=str(row.get('Phone', '')))
        session.add(lead)
        leads.append(lead)

    session.commit()
    return {"message": f"Uploaded {len(leads)} leads"}

@app.get("/leads")
def get_leads(session: Session = Depends(get_session)):
    leads = session.exec(select(Lead)).all()
    return leads

@app.post("/start-campaign")
async def start_campaign(session: Session = Depends(get_session)):
    # Queue all pending leads
    leads = session.exec(select(Lead).where(Lead.status == "pending")).all()
    count = 0
    for lead in leads:
        lead.status = "queued"
        session.add(lead)
        await call_queue.put(lead.id)
        count += 1
    session.commit()
    return {"message": f"Queued {count} calls"}
```

### Task 4: Backend - Webhook & WhatsApp Logic (with Manager Status)

**Files:**
- Modify: `backend/main.py`

**Step 1: Twilio Helper & Status Check**
Add to `backend/main.py`:
```python
from twilio.rest import Client

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
MANAGER_PHONE_NUMBER = os.getenv("MANAGER_PHONE_NUMBER")

@app.get("/manager-status")
def get_manager_status():
    # We can't query Twilio sandbox join status directly via API easily without paid add-ons,
    # but we can return the configured numbers so the UI can show instructions.
    return {
        "connected": True, # Mock for demo, or implement a ping check if feasible
        "join_code": "join outcome-table", # Example code
        "sandbox_number": TWILIO_FROM_NUMBER
    }

def send_whatsapp_summary(lead_name: str, summary: str):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message_body = f"🏠 *New Hot Lead: {lead_name}*\n\n📝 *Summary*: {summary}"

    try:
        message = client.messages.create(
            from_=TWILIO_FROM_NUMBER,
            body=message_body,
            to=MANAGER_PHONE_NUMBER
        )
        return message.sid
    except Exception as e:
        print(f"Twilio Error: {e}")
        return None
```

**Step 2: Webhook Handler (Decrement Active Calls)**
Add to `backend/main.py`:
```python
@app.post("/webhook/vapi")
async def vapi_webhook(payload: dict, session: Session = Depends(get_session)):
    global active_calls
    message = payload.get("message", {})
    type = message.get("type")

    if type == "end-of-call-report":
        # Call finished, decrement counter to allow next call in queue
        active_calls = max(0, active_calls - 1)

        call_id = message.get("call", {}).get("id")
        analysis = message.get("analysis", {})
        summary = analysis.get("summary", "No summary provided")
        ended_reason = message.get("endedReason", "")

        statement = select(Lead).where(Lead.call_id == call_id)
        results = session.exec(statement)
        lead = results.first()

        if lead:
            if "voicemail" in ended_reason.lower():
                lead.status = "voicemail"
            else:
                lead.status = "completed"

            lead.summary = summary
            # Simple keyword matching for interest
            is_interested = any(word in summary.lower() for word in ["interested", "visit", "schedule", "buying", "budget"])
            lead.interest_level = "high" if is_interested else "low"

            session.add(lead)
            session.commit()

            if is_interested and lead.status != "voicemail":
                send_whatsapp_summary(lead.name, summary)

    return {"status": "ok"}
```

### Task 5: Frontend - UI with Status Indicators

**Files:**
- Modify: `frontend/src/App.jsx`

**Step 1: Dashboard UI with WhatsApp Status**
Replace `frontend/src/App.jsx`:
```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Phone, Upload, MessageCircle, Play, Pause } from 'lucide-react';

const API_URL = 'http://localhost:8000';

function App() {
  const [leads, setLeads] = useState([]);
  const [file, setFile] = useState(null);
  const [managerStatus, setManagerStatus] = useState(null);

  useEffect(() => {
    fetchLeads();
    fetchManagerStatus();
    const interval = setInterval(fetchLeads, 2000); // Fast polling for demo
    return () => clearInterval(interval);
  }, []);

  const fetchLeads = async () => {
    try {
      const res = await axios.get(`${API_URL}/leads`);
      setLeads(res.data);
    } catch (err) { console.error(err); }
  };

  const fetchManagerStatus = async () => {
    try {
      const res = await axios.get(`${API_URL}/manager-status`);
      setManagerStatus(res.data);
    } catch (err) { console.error(err); }
  };

  const handleUpload = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    await axios.post(`${API_URL}/upload`, formData);
    fetchLeads();
  };

  const startCampaign = async () => {
    await axios.post(`${API_URL}/start-campaign`);
    fetchLeads();
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8 font-sans">
      <div className="max-w-5xl mx-auto">
        <header className="mb-8 flex justify-between items-center">
            <div>
                <h1 className="text-3xl font-bold text-gray-900">Parmar Properties AI Agent</h1>
                <p className="text-gray-600">Automated Lead Qualification Dashboard</p>
            </div>
            {managerStatus && (
                <div className="bg-green-50 border border-green-200 p-4 rounded-lg flex items-center gap-3">
                    <MessageCircle className="text-green-600" />
                    <div className="text-sm">
                        <p className="font-semibold text-green-800">WhatsApp Sandbox Active</p>
                        <p className="text-green-700">Send <span className="font-mono bg-white px-1 rounded">{managerStatus.join_code}</span> to {managerStatus.sandbox_number}</p>
                    </div>
                </div>
            )}
        </header>

        {/* Upload & Actions */}
        <div className="bg-white p-6 rounded-lg shadow mb-8 flex items-end gap-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-2">Upload Leads CSV</label>
            <div className="flex gap-2">
                <input
                type="file"
                accept=".csv"
                onChange={(e) => setFile(e.target.files[0])}
                className="border p-2 rounded w-full text-sm"
                />
                <button
                onClick={handleUpload}
                className="bg-gray-100 text-gray-700 px-4 py-2 rounded hover:bg-gray-200 flex items-center gap-2"
                >
                <Upload size={16} /> Upload
                </button>
            </div>
          </div>

          <button
            onClick={startCampaign}
            className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 flex items-center gap-2 h-10 font-medium shadow-md transition-all active:scale-95"
          >
            <Play size={18} /> Start Campaign
          </button>
        </div>

        {/* Leads List */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-100 border-b">
              <tr>
                <th className="text-left p-4 text-sm font-semibold text-gray-600">Name</th>
                <th className="text-left p-4 text-sm font-semibold text-gray-600">Phone</th>
                <th className="text-left p-4 text-sm font-semibold text-gray-600">Status</th>
                <th className="text-left p-4 text-sm font-semibold text-gray-600">Summary</th>
              </tr>
            </thead>
            <tbody>
              {leads.length === 0 ? (
                  <tr>
                      <td colSpan="4" className="p-8 text-center text-gray-400">No leads uploaded yet.</td>
                  </tr>
              ) : leads.map(lead => (
                <tr key={lead.id} className="border-t hover:bg-gray-50 transition-colors">
                  <td className="p-4 font-medium">{lead.name}</td>
                  <td className="p-4 text-gray-500 font-mono text-sm">{lead.phone}</td>
                  <td className="p-4">
                    <span className={`px-2 py-1 rounded-full text-xs font-bold uppercase tracking-wider
                      ${lead.status === 'completed' ? 'bg-green-100 text-green-800' :
                        lead.status === 'calling' ? 'bg-blue-100 text-blue-800 animate-pulse' :
                        lead.status === 'queued' ? 'bg-yellow-100 text-yellow-800' :
                        lead.status === 'voicemail' ? 'bg-orange-100 text-orange-800' :
                        lead.status === 'failed' ? 'bg-red-100 text-red-800' :
                        'bg-gray-100 text-gray-600'}`}>
                      {lead.status}
                    </span>
                  </td>
                  <td className="p-4 text-sm text-gray-600 max-w-md truncate">
                    {lead.summary || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default App;
```
