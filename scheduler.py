from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371
    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lng / 2) ** 2
    return 2 * r * asin(sqrt(a))


def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def suggest_slots(date_str, day_start_hour, day_end_hour, duration_minutes, busy_slots, existing_bookings, target_lat, target_lng):
    base_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start = base_date.replace(hour=day_start_hour, minute=0, second=0)
    end = base_date.replace(hour=day_end_hour, minute=0, second=0)
    cursor = start
    duration = timedelta(minutes=duration_minutes)

    slots = []
    while cursor + duration <= end:
        candidate_start = cursor
        candidate_end = cursor + duration

        is_busy = any(overlaps(candidate_start, candidate_end, b["start"], b["end"]) for b in busy_slots)
        if not is_busy:
            local_busy = False
            travel_minutes = 20
            for booking in existing_bookings:
                b_start = datetime.fromisoformat(booking["starts_at"])
                b_end = datetime.fromisoformat(booking["ends_at"])
                if overlaps(candidate_start, candidate_end, b_start, b_end):
                    local_busy = True
                    break
                if booking["lat"] is not None and booking["lng"] is not None:
                    km = haversine_km(booking["lat"], booking["lng"], target_lat, target_lng)
                    est = int((km / 40) * 60)
                    travel_minutes = max(travel_minutes, min(est, 90))

            if not local_busy:
                slots.append(
                    {
                        "starts_at": candidate_start.isoformat(),
                        "ends_at": candidate_end.isoformat(),
                        "travel_minutes": travel_minutes,
                        "score": max(0, 100 - travel_minutes),
                    }
                )

        cursor += timedelta(minutes=30)

    return sorted(slots, key=lambda x: (-x["score"], x["starts_at"]))[:5]
