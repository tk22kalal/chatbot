import os
import json
import time
import asyncio
from datetime import datetime
from aiohttp import web, WSMsgType
from config import PORT

# ── Absolute URL helper ───────────────────────────────────────────────────────
def _abs_photo_url(photo_url: str) -> str:
    """
    Convert a legacy relative photo_url (e.g. /static/uploads/x.jpg) to an
    absolute URL using WEB_URL so old MongoDB records work in Telegram WebView.
    Already-absolute URLs and empty strings are returned unchanged.
    """
    if not photo_url:
        return photo_url
    if photo_url.startswith("http"):
        return photo_url
    # Relative path — prefix with the public base URL
    base = (os.environ.get("WEB_URL") or "").strip().rstrip("/")
    if not base:
        return photo_url          # Can't fix without WEB_URL — return as-is
    if not base.startswith("http"):
        base = f"https://{base}"
    return f"{base}{photo_url}"


from database.database import (
    add_gupshup_user, get_gupshup_user, update_gupshup_profile,
    save_gupshup_message, get_group_messages
)

# ── Connection registry ───────────────────────────────────────────────────────
# connection_key = "{user_id}_{group_name}"
active_connections: dict = {}   # key  -> WebSocketResponse
group_connections: dict  = {}   # group_name -> set of keys  (O(1) lookup)

# ── In-memory user profile cache ─────────────────────────────────────────────
_user_cache: dict = {}
_CACHE_TTL = 300  # seconds before re-fetching from DB

# ── HTML template — loaded once at startup ────────────────────────────────────
_html_cache: str = None


def _get_html() -> str:
    global _html_cache
    if _html_cache is None:
        with open('templates/gupshup.html', 'r') as f:
            _html_cache = f.read()
    return _html_cache


# ── User cache helpers ────────────────────────────────────────────────────────

async def _cached_user(user_id):
    """Return user profile from memory cache; fall back to DB on miss/expiry."""
    now = time.monotonic()
    entry = _user_cache.get(user_id)
    if entry and (now - entry.get('_at', 0)) < _CACHE_TTL:
        return entry
    user = await get_gupshup_user(user_id)
    if user:
        user['_at'] = now
        _user_cache[user_id] = user
    return user


def _cache_set(user_id, display_name: str, photo_url: str):
    """Write-through: keep cache in sync when a profile changes."""
    entry = dict(_user_cache.get(user_id, {}))
    entry.update(display_name=display_name, photo_url=photo_url, _at=time.monotonic())
    _user_cache[user_id] = entry


# ── Connection registry helpers ───────────────────────────────────────────────

def _register(key: str, group: str, ws) -> None:
    active_connections[key] = ws
    group_connections.setdefault(group, set()).add(key)


def _unregister(key: str, group: str) -> None:
    active_connections.pop(key, None)
    if group in group_connections:
        group_connections[group].discard(key)


def get_online_count(group: str) -> int:
    return len(group_connections.get(group, set()))


# ── Fast parallel broadcast ───────────────────────────────────────────────────

async def _send_safe(ws, msg_str: str) -> None:
    try:
        await ws.send_str(msg_str)
    except Exception:
        pass


async def broadcast_to_group(group: str, message: dict, exclude: str = None) -> None:
    """Serialize JSON once, send to all group members in parallel."""
    keys = set(group_connections.get(group, set()))
    if exclude:
        keys.discard(exclude)
    if not keys:
        return

    msg_str = json.dumps(message)
    tasks = []
    dead = []

    for k in keys:
        ws = active_connections.get(k)
        if ws is None:
            dead.append(k)
        else:
            tasks.append(_send_safe(ws, msg_str))

    for k in dead:
        group_connections.get(group, set()).discard(k)

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def broadcast_to_all(message: dict) -> None:
    """Serialize once, send to every connected user in parallel."""
    if not active_connections:
        return
    msg_str = json.dumps(message)
    await asyncio.gather(
        *[_send_safe(ws, msg_str) for ws in list(active_connections.values())],
        return_exceptions=True
    )


# ── Route: serve HTML ─────────────────────────────────────────────────────────

async def index(request):
    return web.Response(
        text=_get_html(),
        content_type='text/html',
        headers={'Cache-Control': 'no-cache, no-store, must-revalidate'}
    )


# ── Route: WebSocket ──────────────────────────────────────────────────────────

async def websocket_handler(request):
    # heartbeat=30 sends a WS ping frame every 30 s → keeps connections alive
    # through Cloudflare and prevents silent drops
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    user_id = None
    group_name = None

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    action = data.get('action')

                    # ── join ──────────────────────────────────────────────
                    if action == 'join':
                        new_uid = data.get('user_id')
                        new_grp = data.get('group')

                        # Leave previous group cleanly if switching
                        if group_name and user_id:
                            _unregister(f"{user_id}_{group_name}", group_name)

                        user_id = new_uid
                        group_name = new_grp
                        conn_key = f"{user_id}_{group_name}"
                        _register(conn_key, group_name, ws)

                        user = await _cached_user(user_id)
                        recent = await get_group_messages(group_name, limit=50)
                        online_count = get_online_count(group_name)

                        # Send history to joining user
                        await ws.send_str(json.dumps({
                            'type': 'history',
                            'messages': recent,
                            'online_count': online_count
                        }))

                        # Notify others in background — don't block the join response
                        asyncio.ensure_future(broadcast_to_group(group_name, {
                            'type': 'user_joined',
                            'user': {
                                'name': (user or {}).get('display_name', 'Anonymous'),
                                'photo': (user or {}).get('photo_url', '')
                            },
                            'online_count': online_count
                        }, exclude=conn_key))

                    # ── message ───────────────────────────────────────────
                    elif action == 'message':
                        if user_id and group_name:
                            user = await _cached_user(user_id)
                            conn_key = f"{user_id}_{group_name}"
                            now = datetime.now()
                            uname  = (user or {}).get('display_name', 'Anonymous')
                            uphoto = (user or {}).get('photo_url', '')
                            text      = data.get('text')
                            image_url = data.get('image_url')
                            gif_url   = data.get('gif_url')

                            # ➡ BROADCAST FIRST — no DB wait
                            await broadcast_to_group(group_name, {
                                'type': 'new_message',
                                'message': {
                                    'user_id':    user_id,
                                    'user_name':  uname,
                                    'user_photo': uphoto,
                                    'text':       text,
                                    'image_url':  image_url,
                                    'gif_url':    gif_url,
                                    'timestamp':  now.isoformat()
                                }
                            }, exclude=conn_key)

                            # ➡ Persist to DB in background
                            asyncio.ensure_future(save_gupshup_message({
                                'user_id':      user_id,
                                'group':        group_name,
                                'display_name': uname,
                                'photo_url':    uphoto,
                                'text':         text,
                                'image_url':    image_url,
                                'gif_url':      gif_url,
                                'timestamp':    now
                            }))

                    # ── leave ─────────────────────────────────────────────
                    elif action == 'leave':
                        lgrp = data.get('group') or group_name
                        luid = data.get('user_id') or user_id
                        if lgrp and luid:
                            _unregister(f"{luid}_{lgrp}", lgrp)
                            if group_name == lgrp:
                                group_name = None
                            luser = await _cached_user(luid)
                            asyncio.ensure_future(broadcast_to_group(lgrp, {
                                'type': 'user_left',
                                'user': {'name': (luser or {}).get('display_name', 'Anonymous')},
                                'online_count': get_online_count(lgrp)
                            }))

                    # ── typing ────────────────────────────────────────────
                    elif action == 'typing':
                        if user_id and group_name:
                            user = await _cached_user(user_id)
                            asyncio.ensure_future(broadcast_to_group(group_name, {
                                'type': 'typing',
                                'user_name': (user or {}).get('display_name', 'Anonymous')
                            }, exclude=f"{user_id}_{group_name}"))

                    # ── update_profile (via WS) ───────────────────────────
                    elif action == 'update_profile':
                        uid      = data.get('user_id') or user_id
                        new_name = (data.get('name') or '').strip()
                        new_photo = data.get('photo_url', '')
                        if uid and new_name:
                            _cache_set(uid, new_name, new_photo)
                            asyncio.ensure_future(update_gupshup_profile(uid, new_name, new_photo))
                            asyncio.ensure_future(broadcast_to_all({
                                'type': 'profile_updated',
                                'user_id': str(uid),
                                'name': new_name,
                                'photo': new_photo
                            }))

                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    print(f"WS action error: {e}")

            elif msg.type == WSMsgType.ERROR:
                print(f'WS connection error: {ws.exception()}')

    finally:
        # Always clean up on disconnect (normal close, error, or timeout)
        if user_id and group_name:
            _unregister(f"{user_id}_{group_name}", group_name)
            user = _user_cache.get(user_id)  # use cache only — no DB on disconnect
            asyncio.ensure_future(broadcast_to_group(group_name, {
                'type': 'user_left',
                'user': {'name': (user or {}).get('display_name', 'Anonymous')},
                'online_count': get_online_count(group_name)
            }))

    return ws


# ── Route: image upload ───────────────────────────────────────────────────────

async def upload_image(request):
    try:
        os.makedirs('static/uploads', exist_ok=True)
        reader = await request.multipart()
        field = await reader.next()
        if field and field.name == 'image':
            filename = f"{int(datetime.now().timestamp())}_{field.filename}"
            filepath = f"static/uploads/{filename}"
            with open(filepath, 'wb') as f:
                while True:
                    chunk = await field.read_chunk()
                    if not chunk:
                        break
                    f.write(chunk)
            return web.json_response({'url': f'/static/uploads/{filename}'})
        return web.json_response({'error': 'No image provided'}, status=400)
    except Exception as e:
        print(f"Upload error: {e}")
        return web.json_response({'error': str(e)}, status=500)


# ── Route: GET /api/user ──────────────────────────────────────────────────────

async def get_user_data(request):
    user_id       = request.query.get('user_id')
    tg_first_name = request.query.get('first_name', '').strip()
    tg_username   = request.query.get('username', '').strip()
    tg_photo_url  = request.query.get('photo_url', '').strip()

    if not user_id:
        return web.json_response({'error': 'Invalid user_id'}, status=400)

    try:
        try:
            user_id_key = int(user_id)
        except (ValueError, TypeError):
            user_id_key = user_id

        user = await get_gupshup_user(user_id_key)
        if user:
            current_name = user.get('display_name', '')
            is_default   = not current_name or current_name == f'User{user_id_key}'
            # Normalise any legacy relative photo_url to absolute on the fly
            stored_photo = _abs_photo_url(user.get('photo_url', ''))
            if tg_first_name and is_default:
                new_photo = tg_photo_url or stored_photo
                await update_gupshup_profile(user_id_key, tg_first_name, new_photo)
                _cache_set(user_id_key, tg_first_name, new_photo)
                user['display_name'] = tg_first_name
                user['photo_url']    = new_photo
            else:
                user['photo_url'] = stored_photo
                _cache_set(user_id_key, user.get('display_name', ''), stored_photo)

            return web.json_response({
                'user_id':           user['_id'],
                'display_name':      user.get('display_name', f'User{user_id_key}'),
                'photo_url':         user.get('photo_url', ''),
                'telegram_username': user.get('telegram_username', '')
            })
        else:
            display_name = tg_first_name or f'User{user_id_key}'
            photo        = _abs_photo_url(tg_photo_url)
            await add_gupshup_user(user_id_key, tg_username, display_name, photo)
            _cache_set(user_id_key, display_name, photo)
            return web.json_response({
                'user_id':           user_id_key,
                'display_name':      display_name,
                'photo_url':         photo,
                'telegram_username': tg_username
            })

    except Exception as e:
        print(f"get_user_data error: {e}")
    return web.json_response({'error': 'Invalid user_id'}, status=400)


# ── Route: POST /api/user/update ──────────────────────────────────────────────

async def update_user_profile(request):
    try:
        data         = await request.json()
        user_id      = data.get('user_id')
        display_name = (data.get('display_name') or '').strip()
        photo_url    = data.get('photo_url', '')

        if not user_id:
            return web.json_response({'error': 'Missing user_id'}, status=400)
        if not display_name:
            return web.json_response({'error': 'display_name cannot be empty'}, status=400)

        try:
            user_id_key = int(user_id)
        except (ValueError, TypeError):
            user_id_key = user_id

        # Write-through cache update — instant for all subsequent lookups
        _cache_set(user_id_key, display_name, photo_url)

        # DB write in background — don't block the HTTP response
        asyncio.ensure_future(update_gupshup_profile(user_id_key, display_name, photo_url))

        # Notify all connected users of the name/photo change
        asyncio.ensure_future(broadcast_to_all({
            'type':    'profile_updated',
            'user_id': str(user_id_key),
            'name':    display_name,
            'photo':   photo_url
        }))

        return web.json_response({'success': True, 'display_name': display_name})
    except Exception as e:
        print(f"update_user_profile error: {e}")
        return web.json_response({'error': str(e)}, status=500)


# ── App factory ───────────────────────────────────────────────────────────────

async def create_app():
    app = web.Application()
    app.router.add_get('/',                 index)
    app.router.add_get('/ws',               websocket_handler)
    app.router.add_post('/upload',          upload_image)
    app.router.add_get('/api/user',         get_user_data)
    app.router.add_post('/api/user/update', update_user_profile)
    app.router.add_static('/static/', path='static', name='static')
    return app


def run_webserver():
    import asyncio
    async def _run():
        app = await create_app()
        web.run_app(app, host='0.0.0.0', port=int(PORT))
    asyncio.run(_run())


if __name__ == '__main__':
    run_webserver()
