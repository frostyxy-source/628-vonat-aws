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
from functools import lru_cache
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

# Simple in-memory cache to avoid hammering the API
_cache: dict = {}
CACHE_TTL = 30  # seconds


def _cached(key: str, ttl: int = CACHE_TTL):
    """Returns (hit, value) from cache."""
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
    """
    Calls GetVonatLista and finds today's VonatID for train 2379.
    The VonatID changes daily (it includes a date suffix).
    Cached for 10 minutes since it won't change during the day.
    """
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
    """
    Returns real-time status of train 2379:
    {
        "vonatszam": "2379",
        "keses_perc": 4,          # delay in minutes (0 = on time)
        "sebesseg": 72,           # km/h
        "lat": 47.71,
        "lon": 19.12,
        "viszonylat": "Vác → Budapest-Nyugati",
        "found": True
    }
    Returns None if train not found or API is down.
    """
    hit, val = _cached("train_status")
    if hit:
        return val

    data = await _post("GetVonatok", BASE_PAYLOAD)
    if not data:
        return None

    trains = data.get("Vonatok", [])
    for t in trains:
        if str(t.get("Vonatszam", "")).strip() == TRAIN_NUMBER:
            result = {
                "found": True,
                "vonatszam": TRAIN_NUMBER,
                "keses_perc": t.get("Keses", 0),
                "sebesseg": t.get("Sebesseg", 0),
                "lat": t.get("GpsLat"),
                "lon": t.get("GpsLon"),
                "vonat_id": t.get("VonatID", ""),
            }
            _set_cache("train_status", result)
            return result

    # Train not in active list (not running right now)
    result = {"found": False, "vonatszam": TRAIN_NUMBER}
    _set_cache("train_status", result)
    return result


def format_status_for_chatbot(status: dict | None) -> str:
    """
    Formats the train status into a short Hungarian string
    that can be injected into the chatbot's system prompt context.
    """
    if status is None:
        return "A valós idejű vonatkövetés most nem elérhető (MÁV API nem válaszol)."

    if not status.get("found"):
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
        keses_str = f"{abs(keses)} perccel korábban jár"  # rare but possible

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
    """
    Drop-in function for main.py — returns a one-liner status string
    to append to the system prompt context.
    """
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