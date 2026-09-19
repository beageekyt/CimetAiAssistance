# SETUP.md — everything needed to reproduce and run this project

Follow top to bottom. Replace `<...>` with your own values. **Never paste real keys into tracked files.**

## 0. Accounts you need

1. **Vapi** — https://vapi.ai (voice pipeline). Get the **Private key** and **Public key** from Dashboard → API Keys.
2. **Vobiz** — https://www.vobiz.ai (Indian SIP trunk + phone number). Complete signup and KYC. You get:
   a DID number, a SIP domain (`<id>.sip.vobiz.ai`), and SIP username/password.
3. **Oracle Cloud** free VM (or any Linux VPS) with a public IP for the backend, for real PSTN calls
   (Vapi requires a public HTTPS webhook URL).
4. **Groq** or **Anthropic** (optional) — only needed for the offline text-chat testing path.

## 1. Local project

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env

cd ..\frontend
npm install
Copy-Item .env.example .env
```

## 2. Backend config (`backend/.env`)

1. `VAPI_API_KEY=<vapi private key>`
2. `VAPI_PUBLIC_KEY=<vapi public key>`
3. `HUMAN_HANDOFF_NUMBER=+91...` (the human's number, E.164; change any time, see step 8)
4. `HUMAN_AGENT_NAME=Aarav`
5. `ENFORCE_CALLING_HOURS=false`
6. Leave `VAPI_ASSISTANT_ID` / `VAPI_PHONE_NUMBER_ID` blank for now; filled in steps 4–5.

You can run and demo the whole journey engine locally without any of the above via the text-chat
endpoints (see step 9a) — the Vapi/Vobiz steps below are only needed for real phone calls.

## 3. Run the backend locally

```powershell
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Check: `http://localhost:8000/api/health` → `{"status":"ok"}`.

## 4. Run the frontend locally

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`. The console will show the lead queue and connect to the SSE stream
("Live feed" badge turns green).

## 5. Deploy the backend on a VM (needed for real PSTN calls — Vapi requires HTTPS)

1. SSH in: `ssh -i <your-key> ubuntu@<vm-ip>`
2. Install Python 3.11, create `~/app`, copy `backend/app` to `~/app/app`, make a venv at `~/app/venv`, `pip install -r requirements.txt`.
3. Copy your `.env` to `~/app/.env`.
4. Create a systemd unit `cimet-backend` running `~/app/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080` from `~/app`, `EnvironmentFile=~/app/.env`; `systemctl enable --now cimet-backend`.
5. Install **Caddy** with a site block `<vm-ip-with-dashes>.nip.io { reverse_proxy 127.0.0.1:8080 }`. Caddy gets a Let's Encrypt cert automatically.
6. Open ports 80 and 443 in the VM's cloud firewall **and** the OS firewall (`sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT`, same for 80).
7. Check: `curl https://<host>.nip.io/api/health` → `{"status":"ok"}`.

To redeploy after code changes: copy `backend/app/` to `~/app/app/`, then `sudo systemctl restart cimet-backend`.

## 6. Connect Vobiz to Vapi (real phone calls)

1. In Vobiz console, note SIP domain, username, password and your DID.
2. In Vapi: Dashboard → **Phone Numbers → Import → BYO SIP trunk**.
   - Create a **SIP trunk credential** with the Vobiz SIP domain as gateway, and the username/password.
   - Import the DID number using that credential.
3. Copy the phone number's **id** → `VAPI_PHONE_NUMBER_ID` in `backend/.env` (and `~/app/.env` on the VM).

## 7. Create / update the assistant on Vapi

```powershell
cd backend
python scripts/create_assistant.py https://<host>.nip.io
```

First run creates the assistant and writes `VAPI_ASSISTANT_ID` into `backend/.env` and
`frontend/.env`. Later runs **PATCH the same assistant** (id stays the same). Re-run whenever you
change `energy_journey.json`, `journey/prompt.py`, or `HUMAN_HANDOFF_NUMBER`. Pass `--new` to force
creating a fresh assistant instead of patching.

The assistant's server URL is `https://<host>.nip.io/api/vapi/webhook`, with tools `record_field`,
`flag_capture_problem`, `log_outcome`, `escalate_to_human`, `complete_journey`, plus the built-in
`endCall` / `transferCall`.

## 8. Frontend config for real calls (`frontend/.env`)

1. `VITE_VAPI_PUBLIC_KEY=<vapi public key>`
2. `VITE_VAPI_ASSISTANT_ID=<assistant id>`
3. `VITE_API_BASE_URL=https://<host>.nip.io`
4. `npm run dev` (or build + host on Vercel/Netlify with the same three env vars).

## 9. What the running system does (per call)

1. Console **Call** (or **Run next (cron)**) → `POST /api/vapi/leads/{id}/call`.
2. Backend runs the **DNC gate** (ACMA register stub, internal opt-out list, calling hours). Blocked → no dial, recorded as `blocked`.
3. Backend calls Vapi `POST /call` with the lead's context (first name, resume section, metadata linking back to the internal call id).
4. Ava opens with recording/consent disclosure. No data is stored until consent = yes; "no" → thank, log, end.
5. Ava collects fields for the section the customer dropped at. Every answer goes through `record_field`; the server validates/normalises it and tells Ava what to ask next.
6. Same field fails 3 times → automatic escalation. Anger, request for a person, advice request, sensitive topic (payment disputes, life-support, vulnerability) → escalation; the server also scans transcripts as a safety net (`journey/signals.py`).
7. Card numbers spoken aloud are redacted (Luhn check) and never stored; Ava redirects to a secure link.
8. Escalation → `escalate_to_human` prepares a briefing (shown in the console Handoff card) and the assistant calls the built-in `transferCall` to `HUMAN_HANDOFF_NUMBER`.
9. All required fields captured + customer confirms → `complete_journey` → sandbox submission → reference shown → close script.
10. Metrics bar updates (completion, escalation rate, estimated human time avoided vs assumed manual baseline).

### 9a. Testing without any Vapi/Vobiz keys (text-chat simulation)

```powershell
# start a simulated call for a lead
curl -X POST http://localhost:8000/api/chat/start -H "Content-Type: application/json" -d "{\"lead_id\": \"L-1001\"}"

# answer the current field (repeat, using the call_id from the previous response)
curl -X POST http://localhost:8000/api/chat/message -H "Content-Type: application/json" -d "{\"call_id\": \"<call_id>\", \"text\": \"yes\"}"
```

This drives the exact same validation/escalation/tool-handler code the real webhook uses, and the
call appears live in the console (open `http://localhost:5173` while you do this).

## 10. Changing the human handoff number

1. Edit `HUMAN_HANDOFF_NUMBER` in `backend/.env` (local) **and** `~/app/.env` on the VM.
2. `python scripts/create_assistant.py https://<host>.nip.io` (pushes the new transfer destination to Vapi).
3. `sudo systemctl restart cimet-backend` on the VM.

## 11. Test checklist (dry run)

1. `GET /api/health` ok; console header shows "Live feed" green.
2. Call L-1001 (your own phone, once Vapi/Vobiz are wired up). Give consent, answer 2–3 fields, deliberately give an invalid email.
3. Second call: say "I want to speak to a person" → handoff card + transfer to the handoff number.
4. Third call: say "not interested" → thanked, logged, lead suppressed.
5. Try L-1004 → **blocked by DNC** before dialling.
6. Complete one full journey → submission reference appears.
7. Before a demo: delete `backend/app/data/calls.json` (VM: `~/app/app/data/calls.json`) and restart, so metrics start clean.

## 12. Hackathon-day swaps

1. Replace the field list in `backend/app/journey/energy_journey.json`.
2. Replace `backend/app/data/leads.json` with the provided synthetic dataset.
3. Set `JOURNEY_SANDBOX_URL`; adapt `routers/sandbox.py::build_payload` to the expected payload.
4. Re-run step 7, then a full dry run.

## 13. Security notes

- Keys/credentials live only in `.env` files (git-ignored). Consider `VAPI_WEBHOOK_SECRET` for the webhook.
- Rotate the Vapi keys, SIP password and SSH key after the hackathon.
- Test data only; do not dial real customers.
