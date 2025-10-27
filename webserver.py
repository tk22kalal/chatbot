import os
import json
import asyncio
from datetime import datetime
from aiohttp import web, WSMsgType
from config import PORT
from database.database import (
    gupshup_users, gupshup_messages, gupshup_groups,
    add_gupshup_user, get_gupshup_user, update_gupshup_profile,
    save_gupshup_message, get_group_messages, get_active_users_in_group
)

active_connections = {}

async def index(request):
    """Serve the main GUPSHUP page"""
    with open('templates/gupshup.html', 'r') as f:
        html_content = f.read()
    return web.Response(text=html_content, content_type='text/html')

def get_online_count(group_name):
    """Get number of users online in a group"""
    count = 0
    for key in active_connections.keys():
        if f"_{group_name}" in key:
            count += 1
    return count

async def websocket_handler(request):
    """Handle WebSocket connections for real-time chat"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    user_id = None
    group_name = None
    
    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
                action = data.get('action')
                
                if action == 'join':
                    user_id = data.get('user_id')
                    group_name = data.get('group')
                    
                    connection_key = f"{user_id}_{group_name}"
                    active_connections[connection_key] = ws
                    
                    user = await get_gupshup_user(user_id)
                    
                    recent_messages = await get_group_messages(group_name, limit=50)
                    online_count = get_online_count(group_name)
                    
                    await ws.send_json({
                        'type': 'history',
                        'messages': recent_messages,
                        'online_count': online_count
                    })
                    
                    await broadcast_to_group(group_name, {
                        'type': 'user_joined',
                        'user': {
                            'name': user.get('display_name', 'Anonymous'),
                            'photo': user.get('photo_url', '')
                        },
                        'online_count': online_count
                    }, exclude=connection_key)
                
                elif action == 'message':
                    if user_id and group_name:
                        user = await get_gupshup_user(user_id)
                        message_data = {
                            'user_id': user_id,
                            'group': group_name,
                            'text': data.get('text'),
                            'image_url': data.get('image_url'),
                            'gif_url': data.get('gif_url'),
                            'timestamp': datetime.now()
                        }
                        
                        await save_gupshup_message(message_data)
                        
                        broadcast_data = {
                            'type': 'new_message',
                            'message': {
                                'user_id': user_id,
                                'user_name': user.get('display_name', 'Anonymous'),
                                'user_photo': user.get('photo_url', ''),
                                'text': data.get('text'),
                                'image_url': data.get('image_url'),
                                'gif_url': data.get('gif_url'),
                                'timestamp': datetime.now().isoformat()
                            }
                        }
                        
                        # Exclude sender from broadcast since they already have the optimistic message
                        connection_key = f"{user_id}_{group_name}"
                        await broadcast_to_group(group_name, broadcast_data, exclude=connection_key)
                
                elif action == 'typing':
                    if user_id and group_name:
                        user = await get_gupshup_user(user_id)
                        connection_key = f"{user_id}_{group_name}"
                        await broadcast_to_group(group_name, {
                            'type': 'typing',
                            'user_name': user.get('display_name', 'Anonymous')
                        }, exclude=connection_key)
                
                elif action == 'update_profile':
                    user_id = data.get('user_id')
                    new_name = data.get('name')
                    new_photo = data.get('photo_url')
                    
                    await update_gupshup_profile(user_id, new_name, new_photo)
                    
                    for key, conn in active_connections.items():
                        if key.startswith(f"{user_id}_"):
                            await broadcast_to_all({
                                'type': 'profile_updated',
                                'user_id': user_id,
                                'name': new_name,
                                'photo': new_photo
                            })
            
            except json.JSONDecodeError:
                pass
        
        elif msg.type == WSMsgType.ERROR:
            print(f'WebSocket error: {ws.exception()}')
    
    if user_id and group_name:
        connection_key = f"{user_id}_{group_name}"
        if connection_key in active_connections:
            del active_connections[connection_key]
        
        user = await get_gupshup_user(user_id)
        online_count = get_online_count(group_name)
        
        await broadcast_to_group(group_name, {
            'type': 'user_left',
            'user': {
                'name': user.get('display_name', 'Anonymous') if user else 'Anonymous'
            },
            'online_count': online_count
        })
    
    return ws

async def broadcast_to_group(group_name, message, exclude=None):
    """Broadcast message to all users in a specific group"""
    for key, ws in list(active_connections.items()):
        if f"_{group_name}" in key and key != exclude:
            try:
                await ws.send_json(message)
            except:
                if key in active_connections:
                    del active_connections[key]

async def broadcast_to_all(message):
    """Broadcast message to all connected users"""
    for ws in list(active_connections.values()):
        try:
            await ws.send_json(message)
        except:
            pass

async def upload_image(request):
    """Handle image uploads"""
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

async def get_user_data(request):
    """Get user data endpoint"""
    user_id = request.query.get('user_id')
    if user_id:
        try:
            user_id_int = int(user_id)
            user = await get_gupshup_user(user_id_int)
            if user:
                return web.json_response({
                    'user_id': user['_id'],
                    'display_name': user.get('display_name', f'User{user_id_int}'),
                    'photo_url': user.get('photo_url', ''),
                    'telegram_username': user.get('telegram_username', '')
                })
            else:
                await add_gupshup_user(user_id_int, None, f'User{user_id_int}', None)
                return web.json_response({
                    'user_id': user_id_int,
                    'display_name': f'User{user_id_int}',
                    'photo_url': '',
                    'telegram_username': ''
                })
        except Exception as e:
            print(f"Error in get_user_data: {e}")
    return web.json_response({'error': 'Invalid user_id'}, status=400)

async def update_user_profile(request):
    """Update user profile (name and photo)"""
    try:
        data = await request.json()
        user_id = data.get('user_id')
        display_name = data.get('display_name')
        photo_url = data.get('photo_url')
        
        if user_id:
            await update_gupshup_profile(int(user_id), display_name, photo_url)
            return web.json_response({'success': True})
        
        return web.json_response({'error': 'Missing user_id'}, status=400)
    except Exception as e:
        print(f"Error updating profile: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def create_app():
    """Create and configure the web application"""
    app = web.Application()
    
    app.router.add_get('/', index)
    app.router.add_get('/ws', websocket_handler)
    app.router.add_post('/upload', upload_image)
    app.router.add_get('/api/user', get_user_data)
    app.router.add_post('/api/user/update', update_user_profile)
    
    app.router.add_static('/static/', path='static', name='static')
    
    return app

def run_webserver():
    """Run the web server"""
    app = create_app()
    web.run_app(app, host='0.0.0.0', port=int(PORT))

if __name__ == '__main__':
    run_webserver()
