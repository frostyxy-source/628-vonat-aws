"""
MÁV train tracker for the 6:28-as zónázó vonat (train number 2379).
Uses the unofficial MÁV VIM REST API (reverse-engineered from the Vonatinfó app).

Endpoints used:
  - GetVonatLista  → find today's VonatID for train 2379
  - GetVonatok     → get real-time GPS position + delay for all trains

Base URL (production): https://vim.mav-start.hu/VIM/PR/20250529/MobileService.svc/rest/
"""

import httpx
import asyncio
from datetime import datetime, date
import pytz
import time

# ── Constants ──────────────────────────────────────────────────────────────────
MAV_BASE_URL = "https://vim.mav-start.hu/VIM/PR/20250529/MobileService.svc/rest/"
UAID = "2Juija1mabqr24Blkx1qkXxJ105j"
TRAIN_NUMBER = "2379"
TZ = pytz.timezone("Europe/Budapest")

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
}

BASE_PAYLOAD = {"Nyelv": "HU", "UAID": UAID}

# ── In-memory cache ────────────────────────────────────────────────────────────
_cache: dict = {}
CACHE_TTL = 30  # seconds

# ── Today's journey memory ─────────────────────────────────────────────────────
# Persists for the day so afternoon users can ask "késtél ma?"
_today_journey: dict = {
    "date": None,          # date the data was recorded
    "seen": False,         # did we see the train running today?
    "max_keses": 0,        # peak delay observed during the journey
    "arrived": False,      # did the train finish its journey?
    "on_time": False,      # was it on time (0 min delay throughout)?
}


def _update_journey_memory(keses: int):
    """Called every time we see the train running. Records today's delay."""
    today = date.today().isoformat()
    if _today_journey["date"] != today:
        # New day — reset
        _today_journey["date"] = today
        _today_journey["seen"] = False
        _today_journey["max_keses"] = 0
        _today_journey["arrived"] = False
        _today_journey["on_time"] = False

    _today_journey["seen"] = True
    if keses > _today_journey["max_keses"]:
        _today_journey["max_keses"] = keses
    if keses == 0 and not _today_journey["arrived"]:
        _today_journey["on_time"] = True


def _mark_arrived():
    """Called when train disappears from active list after being seen."""
    if _today_journey["seen"]:
        _today_journey["arrived"] = True
        print(f"[TRACKER] Train arrived. Max delay today: {_today_journey['max_keses']} min", flush=True)


def get_today_summary() -> str | None:
    """
    Returns a summary of today's journey for afternoon queries like 'késtél ma?'
    Returns None if we haven't seen the train today at all.
    """
    today = date.today().isoformat()
    if _today_journey["date"] != today or not _today_journey["seen"]:
        return None

    keses = _today_journey["max_keses"]

    if not _today_journey["arrived"]:
        # Still running
        return None

    if keses == 0:
        return "MA REGGEL: Pontosan érkeztem. Ez is megtörténik néha. Ne szokd meg."
    elif keses <= 3:
        return f"MA REGGEL: {keses} percet késtem. Semmi különös. A váltó. Mindig a váltó."
    elif keses <= 10:
        return f"MA REGGEL: {keses} percet késtem. Az időjárás hibája. Vagy a pályáé. Nem az enyém."
    else:
        return f"MA REGGEL: {keses} percet késtem. Igen. De ezt most ne tárgyaljuk."


# ── Cache helpers ──────────────────────────────────────────────────────────────
def _cached(key: str, ttl: int = CACHE_TTL):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < ttl:
        return True, entry["value"]
    return False, None


def _set_cache(key: str, value):
    _cache[key] = {"ts": time.time(), "value": value}


# ── API helpers ────────────────────────────────────────────────────────────────
async def _post(endpoint: str, payload: dict) -> dict | None:
    url = MAV_BASE_URL + endpoint
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(url, headers=HEADERS, json=payload)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[MAV API ERROR] {endpoint}: {e}", flush=True)
        return None


# ── Core functions ─────────────────────────────────────────────────────────────
async def get_today_vonat_id() -> str | None:
    cache_key = f"vonat_id_{date.today().isoformat()}"
    hit, val = _cached(cache_key, ttl=600)
    if hit:
        return val

    data = await _post("GetVonatLista", BASE_PAYLOAD)
    if not data:
        return None

    trains = data.get("Vonatok", [])
    for t in trains:
        if str(t.get("Vonatszam", "")).strip() == TRAIN_NUMBER:
            vonat_id = t.get("VonatID")
            _set_cache(cache_key, vonat_id)
            return vonat_id

    return None


async def get_train_status() -> dict | None:
    hit, val = _cached("train_status")
    if hit:
        return val

    data = await _post("GetVonatok", BASE_PAYLOAD)
    if not data:
        return None

    trains = data.get("Vonatok", [])
    for t in trains:
        if str(t.get("Vonatszam", "")).strip() == TRAIN_NUMBER:
            keses = t.get("Keses", 0)
            result = {
                "found": True,
                "vonatszam": TRAIN_NUMBER,
                "keses_perc": keses,
                "sebesseg": t.get("Sebesseg", 0),
                "lat": t.get("GpsLat"),
                "lon": t.get("GpsLon"),
                "vonat_id": t.get("VonatID", ""),
            }
            # Update today's journey memory every time we see the train
            _update_journey_memory(keses)
            _set_cache("train_status", result)
            return result

    # Train not in active list
    # If we saw it earlier today, mark it as arrived
    if _today_journey["seen"] and not _today_journey["arrived"]:
        _mark_arrived()

    result = {"found": False, "vonatszam": TRAIN_NUMBER}
    _set_cache("train_status", result)
    return result


def format_status_for_chatbot(status: dict | None) -> str:
    if status is None:
        return "A valós idejű vonatkövetés most nem elérhető (MÁV API nem válaszol)."

    if not status.get("found"):
        # Check if we have today's journey data
        summary = get_today_summary()
        if summary:
            return summary
        return (
            "A 2379-es vonat (te, a 6:28-as) most nem fut — "
            "még nem indultál el, vagy már megérkeztél Nyugatiba."
        )

    keses = status.get("keses_perc", 0)
    sebesseg = status.get("sebesseg", 0)

    if keses == 0:
        keses_str = "menetrendszerűen halad"
    elif keses > 0:
        keses_str = f"{keses} percet késik"
    else:
        keses_str = f"{abs(keses)} perccel korábban jár"

    lat = status.get("lat")
    lon = status.get("lon")
    hely_str = f"(GPS: {lat:.4f}, {lon:.4f})" if lat and lon else ""

    return (
        f"VALÓS IDEJŰ ADATOK (frissítve most): "
        f"Te (a 6:28-as, vonatszám: 2379) {keses_str}. "
        f"Sebesség: {sebesseg} km/h. {hely_str}"
    )


# ── FastAPI integration helper ────────────────────────────────────────────────
async def get_train_context_string() -> str:
    try:
        status = await get_train_status()
        return format_status_for_chatbot(status)
    except Exception as e:
        print(f"[TRACKER ERROR] {e}", flush=True)
        return "A vonatkövetés most nem elérhető."


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    async def test():
        print("Fetching train status...")
        status = await get_train_status()
        print("Raw status:", status)
        print("Formatted:", format_status_for_chatbot(status))

        print("\nFetching VonatID...")
        vid = await get_today_vonat_id()
        print("VonatID:", vid)

    asyncio.run(test())
