import json
import os
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _http_json(method: str, url: str, payload=None, headers=None, timeout=10):
    body = None
    req_headers = headers.copy() if headers else {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = Request(url=url, data=body, method=method, headers=req_headers)
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class MapsService:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

    def geocode(self, address: str):
        if self.api_key:
            q = urlencode({"address": address, "key": self.api_key})
            payload = _http_json("GET", f"https://maps.googleapis.com/maps/api/geocode/json?{q}")
            if payload.get("status") == "OK" and payload.get("results"):
                result = payload["results"][0]
                loc = result["geometry"]["location"]
                return {
                    "formatted_address": result["formatted_address"],
                    "lat": loc["lat"],
                    "lng": loc["lng"],
                    "mode": "google",
                }
        lat = float((sum(ord(c) for c in address) % 18000) / 100 - 90)
        lng = float((sum(ord(c) * 3 for c in address) % 36000) / 100 - 180)
        return {
            "formatted_address": address,
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "mode": "demo",
        }


class OutlookService:
    def __init__(self):
        self.tenant = os.getenv("MS_TENANT_ID", "").strip()
        self.client_id = os.getenv("MS_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("MS_CLIENT_SECRET", "").strip()

    @property
    def enabled(self):
        return all([self.tenant, self.client_id, self.client_secret])

    def _token(self):
        token_url = f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"
        form = urlencode(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            }
        ).encode("utf-8")
        req = Request(token_url, data=form, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["access_token"]

    def create_event(self, user_id: str, subject: str, starts_at: str, ends_at: str, address: str, body: str):
        if not self.enabled:
            return {"event_id": None, "mode": "demo"}
        token = self._token()
        payload = {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "start": {"dateTime": starts_at, "timeZone": "UTC"},
            "end": {"dateTime": ends_at, "timeZone": "UTC"},
            "location": {"displayName": address},
            "allowNewTimeProposals": True,
        }
        url = f"https://graph.microsoft.com/v1.0/users/{user_id}/events"
        event = _http_json("POST", url, payload=payload, headers={"Authorization": f"Bearer {token}"})
        return {"event_id": event.get("id"), "mode": "graph"}

    def get_busy_slots(self, user_id: str, start_iso: str, end_iso: str):
        if not self.enabled:
            return []
        token = self._token()
        payload = {
            "schedules": [user_id],
            "startTime": {"dateTime": start_iso, "timeZone": "UTC"},
            "endTime": {"dateTime": end_iso, "timeZone": "UTC"},
            "availabilityViewInterval": 30,
        }
        data = _http_json(
            "POST",
            f"https://graph.microsoft.com/v1.0/users/{user_id}/calendar/getSchedule",
            payload=payload,
            headers={"Authorization": f"Bearer {token}"},
        ).get("value", [])
        if not data:
            return []
        busy = []
        for item in data[0].get("scheduleItems", []):
            busy.append(
                {
                    "start": datetime.fromisoformat(item["start"]["dateTime"]),
                    "end": datetime.fromisoformat(item["end"]["dateTime"]),
                }
            )
        return busy
