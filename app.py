import json
import os
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from db import get_conn, init_db
from integrations import MapsService, OutlookService
from scheduler import suggest_slots
from seed_agents import AGENTS

ROOT = Path(__file__).parent
maps = MapsService()
outlook = OutlookService()


def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    return json.loads(raw.decode("utf-8"))


def write_json(handler, status, payload):
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._serve_file(ROOT / "templates" / "index.html", "text/html")
            return
        if path.startswith("/static/"):
            file_path = ROOT / path[1:]
            mime = "text/plain"
            if path.endswith(".css"):
                mime = "text/css"
            if path.endswith(".js"):
                mime = "application/javascript"
            self._serve_file(file_path, mime)
            return

        if path == "/api/config":
            regions = sorted(list({a["region"] for a in AGENTS}))
            write_json(
                self,
                200,
                {
                    "regions": regions,
                    "integrations": {
                        "google_maps": bool(maps.api_key),
                        "outlook": outlook.enabled,
                    },
                },
            )
            return

        if path == "/api/agents":
            qs = parse_qs(parsed.query)
            region = qs.get("region", [None])[0]
            result = [a for a in AGENTS if not region or a["region"] == region]
            write_json(self, 200, {"agents": result})
            return

        if path == "/api/bookings":
            qs = parse_qs(parsed.query)
            date = qs.get("date", [datetime.now(timezone.utc).date().isoformat()])[0]
            conn = get_conn()
            rows = conn.execute(
                """
                SELECT b.id, b.agent_id, b.starts_at, b.ends_at, b.status,
                       c.full_name, c.phone, c.address, c.region
                FROM bookings b
                JOIN clients c ON c.id = b.client_id
                WHERE date(b.starts_at) = ?
                ORDER BY b.starts_at
                """,
                (date,),
            ).fetchall()
            conn.close()
            write_json(self, 200, {"bookings": [dict(r) for r in rows]})
            return

        write_json(self, 404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/geocode":
            body = read_json(self)
            address = body.get("address", "").strip()
            if not address:
                write_json(self, 400, {"error": "address is required"})
                return
            write_json(self, 200, maps.geocode(address))
            return

        if path == "/api/suggest-slots":
            body = read_json(self)
            region = body.get("region")
            date = body.get("date")
            lat = body.get("lat")
            lng = body.get("lng")
            duration = int(body.get("duration_minutes", 60))
            if not all([region, date, lat is not None, lng is not None]):
                write_json(self, 400, {"error": "region, date, lat, lng are required"})
                return

            region_agents = [a for a in AGENTS if a["region"] == region]
            suggestions = []
            conn = get_conn()
            for agent in region_agents:
                day_start = datetime.fromisoformat(f"{date}T00:00:00+00:00")
                day_end = day_start + timedelta(days=1)
                busy = outlook.get_busy_slots(agent["outlook_user_id"], day_start.isoformat(), day_end.isoformat())

                rows = conn.execute(
                    """
                    SELECT b.starts_at, b.ends_at, c.lat, c.lng
                    FROM bookings b
                    JOIN clients c ON c.id = b.client_id
                    WHERE b.agent_id = ?
                      AND date(b.starts_at) = ?
                    """,
                    (agent["id"], date),
                ).fetchall()
                existing = [dict(r) for r in rows]
                slots = suggest_slots(date, 8, 17, duration, busy, existing, float(lat), float(lng))
                for slot in slots[:3]:
                    suggestions.append({"agent_id": agent["id"], "agent_name": agent["name"], "region": agent["region"], **slot})

            conn.close()
            top = sorted(suggestions, key=lambda x: (-x["score"], x["starts_at"]))[:8]
            write_json(self, 200, {"slots": top})
            return

        if path == "/api/book":
            body = read_json(self)
            required = ["client_name", "client_phone", "address", "region", "lat", "lng", "agent_id", "starts_at", "ends_at"]
            missing = [f for f in required if f not in body]
            if missing:
                write_json(self, 400, {"error": f"missing fields: {', '.join(missing)}"})
                return

            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO clients (full_name, phone, address, region, lat, lng) VALUES (?, ?, ?, ?, ?, ?)",
                (body["client_name"], body["client_phone"], body["address"], body["region"], body["lat"], body["lng"]),
            )
            client_id = cur.lastrowid

            agent = next((a for a in AGENTS if a["id"] == body["agent_id"]), None)
            if not agent:
                conn.rollback()
                conn.close()
                write_json(self, 400, {"error": "invalid agent_id"})
                return

            event = outlook.create_event(
                agent["outlook_user_id"],
                f"Client Meeting: {body['client_name']}",
                body["starts_at"],
                body["ends_at"],
                body["address"],
                body.get("notes", "Booked by Black Cygnet Booking Assistant"),
            )

            cur.execute(
                """
                INSERT INTO bookings (client_id, agent_id, starts_at, ends_at, notes, travel_minutes, outlook_event_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_id,
                    body["agent_id"],
                    body["starts_at"],
                    body["ends_at"],
                    body.get("notes", ""),
                    int(body.get("travel_minutes", 0)),
                    event["event_id"],
                ),
            )
            booking_id = cur.lastrowid
            conn.commit()
            conn.close()
            write_json(self, 201, {"booking_id": booking_id, "outlook_mode": event["mode"]})
            return

        write_json(self, 404, {"error": "Not found"})

    def _serve_file(self, path: Path, content_type: str):
        if not path.exists():
            write_json(self, 404, {"error": "Not found"})
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Server running on http://localhost:{port}")
    server.serve_forever()
