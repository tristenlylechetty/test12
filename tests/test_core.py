from integrations import MapsService
from scheduler import suggest_slots


def test_geocode_demo_mode_has_coordinates():
    maps = MapsService()
    result = maps.geocode('1 Main Road, Cape Town')
    assert 'lat' in result
    assert 'lng' in result
    assert result['mode'] in {'demo', 'google'}


def test_scheduler_returns_ranked_slots():
    slots = suggest_slots(
        date_str='2026-03-26',
        day_start_hour=8,
        day_end_hour=10,
        duration_minutes=60,
        busy_slots=[],
        existing_bookings=[],
        target_lat=-33.9,
        target_lng=18.4,
    )
    assert len(slots) > 0
    assert 'starts_at' in slots[0]
