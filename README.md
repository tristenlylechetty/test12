# Black Cygnet Booking Assistant (MVP)

A lightweight web app to help booking agents schedule Capital Legacy field visits with:

- Address capture and geocoding via Google Maps API
- Region-based agent selection
- Availability-aware slot suggestions
- Outlook calendar event creation via Microsoft Graph API

## Features

- **Booking form UI** for call center agents
- **Smart slot suggestion** with travel + prep buffers
- **SQLite persistence** for clients and bookings
- **Outlook integration** (optional, enabled by env vars)
- **Google geocoding integration** (optional, enabled by env vars)

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open: `http://localhost:8000`

## Configuration

Copy `.env.example` to `.env` and set values.

```bash
cp .env.example .env
```

### Required for Google Maps integration

- `GOOGLE_MAPS_API_KEY`

### Required for Outlook integration (Microsoft Graph)

- `MS_TENANT_ID`
- `MS_CLIENT_ID`
- `MS_CLIENT_SECRET`

> Agent `outlook_user_id` values in `seed_agents.py` should match real mailbox or user IDs.

## API

- `GET /api/config`
- `POST /api/geocode`
- `GET /api/agents?region=Johannesburg`
- `POST /api/suggest-slots`
- `POST /api/book`
- `GET /api/bookings?date=YYYY-MM-DD`

## Notes

- If API keys are missing, the app still works in **demo mode**.
- This is an MVP intended to accelerate your booking workflow.
