"""
Fetches Groq API keys from Supabase `profiles.groq_api_key` column
and serves them in round-robin order.

Requires one-time Supabase SQL setup (run in Supabase SQL Editor):

    CREATE OR REPLACE FUNCTION get_all_groq_keys()
    RETURNS TABLE(groq_api_key TEXT)
    LANGUAGE sql
    SECURITY DEFINER
    AS $$
      SELECT groq_api_key FROM profiles
      WHERE groq_api_key IS NOT NULL AND groq_api_key != '';
    $$;

    GRANT EXECUTE ON FUNCTION get_all_groq_keys() TO anon;
"""

import asyncio
import aiohttp
import os
import time

SUPABASE_URL = "https://txhxgmryxsebqfxoocos.supabase.co"
SUPABASE_KEY = "sb_publishable_Rp_naWKL3nPS-6nlOx1LHw_40Rc4T1M"

_keys: list[str] = []
_index: int = 0
_lock = asyncio.Lock()
_refresh_interval = 300  # re-fetch from Supabase every 5 minutes

# Rate-limit tracking: key -> (timestamp, ttl_seconds)
# Per-minute limit:  ~65 s cooldown
# Daily quota limit: ~24 h cooldown
_rate_limited: dict = {}
_TTL_MINUTE = 65
_TTL_DAILY  = 86400

# Used by probe_valid_key to make a minimal test call
_GROQ_PROBE_URL   = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_PROBE_MODEL = "llama-3.1-8b-instant"


async def _fetch_keys_from_supabase() -> list[str]:
    """Call the Supabase RPC function and return list of groq keys."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/get_all_groq_keys"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json={},
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    keys = [row["groq_api_key"] for row in data
                            if row.get("groq_api_key", "").strip().startswith("gsk_")]
                    print(f"[supabase_keys] Loaded {len(keys)} Groq key(s) from Supabase")
                    return keys
                else:
                    text = await resp.text()
                    print(f"[supabase_keys] RPC error {resp.status}: {text[:300]}")
    except Exception as e:
        print(f"[supabase_keys] Fetch error: {e}")
    return []


async def refresh_keys() -> None:
    """Fetch fresh keys from Supabase and update the in-memory pool."""
    global _keys
    fetched = await _fetch_keys_from_supabase()
    if fetched:
        async with _lock:
            _keys = fetched
    elif not _keys:
        # Fall back to env var if Supabase returns nothing
        env_key = os.environ.get("GROQ_API_KEY", "").strip()
        if env_key:
            async with _lock:
                _keys = [env_key]
            print("[supabase_keys] Falling back to GROQ_API_KEY env var")


async def _background_refresh():
    """Background task: refresh keys every _refresh_interval seconds."""
    while True:
        await asyncio.sleep(_refresh_interval)
        await refresh_keys()


def start_background_refresh():
    """Call once at app startup to kick off periodic key refresh."""
    asyncio.ensure_future(_background_refresh())


def get_next_key() -> str:
    """
    Return the next Groq API key in round-robin order.
    Thread-safe index bump without async (reads are lock-free).
    """
    global _index
    if not _keys:
        return os.environ.get("GROQ_API_KEY", "")
    key = _keys[_index % len(_keys)]
    _index = (_index + 1) % len(_keys)
    slot = (_index) % len(_keys) + 1
    print(f"[supabase_keys] using key slot {slot}/{len(_keys)}")
    return key


def get_all_keys() -> list:
    """
    Return a snapshot of all available keys (Supabase pool + env fallback).
    Used for retry-on-rate-limit iteration.
    """
    env_key = os.environ.get("GROQ_API_KEY", "").strip()
    result  = list(_keys)
    if env_key and env_key not in result:
        result.append(env_key)
    return result


def mark_key_rate_limited(key: str, daily: bool = False) -> None:
    """
    Record that this key just hit a 429.
    daily=True  → 24-hour cooldown (daily quota exhausted)
    daily=False → 65-second cooldown (per-minute rate limit)
    """
    ttl = _TTL_DAILY if daily else _TTL_MINUTE
    _rate_limited[key] = (time.time(), ttl)
    kind = "daily quota" if daily else "per-minute"
    print(f"[supabase_keys] Key marked {kind} rate-limited ({ttl}s cooldown).")


def _is_key_available(key: str) -> bool:
    """Return True if this key is not currently in its cooldown window."""
    entry = _rate_limited.get(key)
    if entry is None:
        return True
    ts, ttl = entry
    return (time.time() - ts) > ttl


def has_valid_key() -> bool:
    """Quick in-memory check: True if at least one key is not in cooldown."""
    return any(_is_key_available(k) for k in get_all_keys())


async def probe_valid_key() -> bool:
    """
    Actually test every non-cooled-down key with a minimal real API call.
    Returns True the moment any key responds 200.
    Keys that return 429 are marked with the appropriate TTL.
    This is the authoritative check used before starting an AI girl session.
    """
    keys = get_all_keys()
    if not keys:
        return False

    for key in keys:
        if not _is_key_available(key):
            continue
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    _GROQ_PROBE_URL,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type":  "application/json",
                    },
                    json={
                        "model":      _GROQ_PROBE_MODEL,
                        "messages":   [{"role": "user", "content": "hi"}],
                        "max_tokens": 1,
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        print(f"[supabase_keys] Probe OK — valid key found.")
                        return True
                    elif resp.status == 429:
                        body = await resp.text()
                        is_daily = any(w in body.lower() for w in ("daily", "quota", "exceeded", "24"))
                        mark_key_rate_limited(key, daily=is_daily)
                    else:
                        print(f"[supabase_keys] Probe got {resp.status}, skipping key.")
        except Exception as e:
            print(f"[supabase_keys] probe error: {e}")

    print("[supabase_keys] Probe: all keys exhausted.")
    return False

