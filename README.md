# CIMET AI Hiring Hackathon 2026 — Ava, the Dropout Recovery Voice Agent

Problem statement (chosen): **"Teach the phone to listen"** (Energy vertical). Ava is an AI voice
agent that **phones customers who dropped out of an econnex Energy comparison journey**, resumes
the journey by voice, validates and submits it, and **hands off to a human** (warm transfer with a
briefing) when it should. A React console shows the whole thing live.

Mode: **B — Agent-Driven** (the agent runs the call end to end). The console is the modernised
supervisor/agent view: it shows the right script at the right time, captures answers automatically,
and measures efficiency against a manual workflow.

Full step-by-step build/setup log: **[SETUP.md](SETUP.md)**.

## Architecture

```
 Console (React)  <--- SSE /api/vapi/stream ---  FastAPI backend  <--- webhook + tool calls ---  Vapi
        |                                              |                                          |
        | Call / Run next  -----------------------> DNC gate -> POST /call ----------------->  Vobiz SIP trunk
        |                                              |                                          |
        |                                        mock journey sandbox                        customer's phone
        v                                                                                    (+ human handoff)
   Browser call (Vapi Web SDK, fallback)
```

- **Vapi** runs STT + LLM + TTS and turn-taking. Outbound PSTN goes through a **Vobiz** SIP trunk
  imported into Vapi as a BYO number (India DID, no Twilio needed).
- **Backend** owns every decision that matters: next field to ask, validation/normalisation,
  consent gating, 3-strike confusion escalation, card-data guard, life-support handling, DNC gate,
  opt-out suppression, sandbox submission, metrics. The LLM only converses; the server is the
  source of truth.
- **Console** = lead queue + live transcript + script card + journey progress + handoff card + metrics.

## What maps to the handout

| Handout requirement | Where |
|---|---|
| Agent places the call, converses, seeks data, completes journey | `routers/vapi.py` `_dial`, tool handlers; assistant built in `journey/prompt.py` |
| Scripts per section and per field (ours to design) | `journey/energy_journey.json` (`script`, `reprompt`, section scripts, escalation/handoff/decline/close scripts) |
| Escalation: anger, confusion, off-script, sensitive, asks-for-person, low confidence | LLM tools + server-side safety net in `journey/signals.py`; 3 failures on one field → escalate |
| Warm handoff with context ("no need to repeat anything") | `escalate_to_human` briefing + `transferCall` (`warm-transfer-say-summary`) + console Handoff card |
| Consent / recording disclosure first (AU two-party) | `consent_recording` is the first field; nothing else is stored until consent = yes |
| No card data by voice | Luhn detector redacts numbers from transcript, never stored; script redirects to secure link |
| No advice | Prompt guardrail + advice signal → escalation |
| DNC / ACMA gate before dialling (stub, show where it sits) | `services/dnc.py`, shown as chips on every call |
| Respect "no" (thank, log, end) | `log_outcome` + suppression list + `endCall` |
| Modernised console, efficiency vs manual | `frontend/src/*`, `services/metrics.py` (baseline assumptions are labelled, replace on the day) |
| Test data only | `data/leads.json` synthetic; AU numbers are ACMA-reserved fictional ranges |

## Run it

Backend (local):

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate      # Windows
pip install -r requirements.txt
cp .env.example .env                                  # fill in keys, see table below
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env    # VITE_VAPI_PUBLIC_KEY, VITE_VAPI_ASSISTANT_ID, VITE_API_BASE_URL
npm run dev             # http://localhost:5173
```

Push the prompt/tools to Vapi (re-run after any script, journey or handoff-number change):

```bash
cd backend
python scripts/create_assistant.py https://<public-https-backend-url>
```

It PATCHes the existing assistant when `VAPI_ASSISTANT_ID` is set (id stays stable); `--new` forces a new one.

Without any Vapi keys at all, you can still exercise the whole journey engine locally through the
text-chat endpoints (`POST /api/chat/start`, `/api/chat/message`, `/api/chat/complete`), which use
the exact same validation/escalation/tool logic as a real call and show up live in the console.

## Configuration (`backend/.env`)

| Variable | Purpose |
|---|---|
| `VAPI_API_KEY` / `VAPI_PUBLIC_KEY` | Vapi private key (backend) / public key (browser calls) |
| `VAPI_ASSISTANT_ID` | Assistant to patch and to use for outbound calls |
| `VAPI_PHONE_NUMBER_ID` | Vapi id of the imported Vobiz number used as caller ID |
| `VAPI_WEBHOOK_SECRET` | Optional; if set, webhook requests must carry `x-vapi-secret` |
| **`HUMAN_HANDOFF_NUMBER`** | **E.164 number Ava warm-transfers to (e.g. `+916397103051`). Change any time: edit `.env`, run `create_assistant.py`, restart backend.** Blank = console-only handoff |
| `HUMAN_AGENT_NAME` | Name used in the handoff line (default Aarav) |
| `ENFORCE_CALLING_HOURS` | `true` makes the DNC gate block calls outside permitted local hours |
| `JOURNEY_SANDBOX_URL` | Real journey-completion endpoint on the day; blank uses the built-in mock |
| `LLM_PROVIDER`, `GROQ_*`, `ANTHROPIC_*` | Only for offline prompt iteration; live call model is set in `journey/prompt.py` |

Secrets live only in `.env` files (git-ignored). Never commit them; rotate all keys after the hackathon.

## Demo script (3 minutes)

1. Open the console. Point at the queue: each lead shows where they dropped and where Ava resumes.
2. **Call** Priya (L-1001, your own phone). Phone rings, Ava discloses recording and asks consent.
3. Answer a few fields; watch transcript, script card and journey progress update with zero typing.
4. Say a wrong value (bad email) → "Bad values caught" ticks; say "I want to talk to a person" →
   handoff card appears with briefing + opening line, and the call transfers to the human number.
5. **Run next (cron)** on the queue: Daniel/Mei etc. Show the DNC-listed lead (L-1004) being **blocked before dialling**.
6. Finish one journey: submission reference shows in the console; metrics bar shows time saved (labelled as assumption).

## On the day (real sandbox / dataset drop)

1. Replace `backend/app/journey/energy_journey.json` field list with the real one (engine is config-driven).
2. Replace `backend/app/data/leads.json` with their synthetic dataset (keep the same keys or adapt `services/leads.py`).
3. Set `JOURNEY_SANDBOX_URL`; adapt `routers/sandbox.py::build_payload` to the expected payload.
4. Confirm the test phone numbers, then run `create_assistant.py` and do one full dry run.

## Project layout

```
backend/app/journey/    schema, energy_journey.json, validate.py, signals.py, prompt.py
backend/app/services/   call_state, dnc, leads, metrics (+ legacy llm.py)
backend/app/routers/    vapi.py (webhook, calls, queue, SSE), sandbox.py (mock journey API), chat.py
backend/app/data/       leads.json, dnc_list.json (calls.json is runtime state, git-ignored)
backend/scripts/        create_assistant.py
frontend/src/           App, LeadQueue, CallPanel, SidePanel, MetricsBar, useConsole, api, types
```

## Known limits / honest notes

- Efficiency numbers compare to an **assumed** manual baseline (25 s/field + 90 s overhead), not a measurement.
- Mode A (agent-assisted console) is not built; Mode B is the focus.
- Warm transfer uses Vapi's `warm-transfer-say-summary`; verify on a live call that the human hears the briefing.
- Sandbox is a mock until the real endpoint is supplied.
