#(©)CodeXBotz - Modified for Anonymous Chat

import pymongo
import os
import random
import string
from config import DB_URI, DB_NAME
from datetime import datetime

try:
    if DB_URI and DB_URI.strip() and DB_URI not in ['', 'url'] and (DB_URI.startswith('mongodb://') or DB_URI.startswith('mongodb+srv://')):
        dbclient = pymongo.MongoClient(DB_URI)
        database = dbclient[DB_NAME]
        print("✅ Connected to MongoDB successfully")
    else:
        if not DB_URI or DB_URI in ['', 'url']:
            print("ℹ️  DATABASE_URL not configured. Using mock database for testing.")
        else:
            print(f"⚠️  Invalid DATABASE_URL format. Using mock database for testing.")
        from database.mock_db import MockDatabase
        database = MockDatabase()
        dbclient = None
except Exception as e:
    print(f"⚠️  Failed to connect to database: {e}")
    print("ℹ️  Using mock database for testing.")
    from database.mock_db import MockDatabase
    database = MockDatabase()
    dbclient = None

user_data = database['users']
chat_data = database['chats']
gupshup_users = database['gupshup_users']
gupshup_messages = database['gupshup_messages']
gupshup_groups = database['gupshup_groups']

def generate_chat_token():
    """Generate a unique 8-character token for chat sessions"""
    while True:
        token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        # Check if token already exists
        if not chat_data.find_one({'token': token}):
            return token

# User Management
async def present_user(user_id: int):
    found = user_data.find_one({'_id': user_id})
    return bool(found)

async def add_user(user_id: int, username: str = None, first_name: str = None):
    user_data.insert_one({
        '_id': user_id,
        'username': username or '',
        'first_name': first_name or '',
        'gender': None,
        'partner_id': None,
        'searching': False,
        'joined_date': datetime.now()
    })
    return

async def get_user(user_id: int):
    return user_data.find_one({'_id': user_id})

async def update_user_gender(user_id: int, gender: str):
    user_data.update_one({'_id': user_id}, {'$set': {'gender': gender}})
    return

async def set_user_searching(user_id: int, searching: bool):
    user_data.update_one({'_id': user_id}, {'$set': {'searching': searching}})
    return

async def set_user_partner(user_id: int, partner_id: int = None):
    user_data.update_one({'_id': user_id}, {'$set': {'partner_id': partner_id if partner_id else None}})
    return

async def get_searching_users():
    """Get all users who are currently searching for a partner"""
    users = user_data.find({'searching': True, 'partner_id': None})
    return list(users)

async def clear_user_chat_state(user_id: int):
    """Clear user's partner and searching status"""
    user_data.update_one(
        {'_id': user_id}, 
        {'$set': {'partner_id': None, 'searching': False}}
    )
    return

# Chat History Management
async def log_chat_start(user1_id: int, user2_id: int):
    """Log when a chat starts between two users and return unique token"""
    token = generate_chat_token()
    
    chat_data.insert_one({
        'token': token,
        'user1_id': user1_id,
        'user2_id': user2_id,
        'start_time': datetime.now(),
        'end_time': None,
        'messages': []
    })
    return token

async def log_message(user1_id: int, user2_id: int, sender_id: int, message_text: str):
    """Log a message in the chat history"""
    # Find active chat between these users
    chat = chat_data.find_one({
        '$or': [
            {'user1_id': user1_id, 'user2_id': user2_id, 'end_time': None},
            {'user1_id': user2_id, 'user2_id': user1_id, 'end_time': None}
        ]
    })
    
    if chat:
        chat_data.update_one(
            {'_id': chat['_id']},
            {'$push': {'messages': {
                'sender_id': sender_id,
                'text': message_text,
                'timestamp': datetime.now()
            }}}
        )
    return

async def end_chat(user1_id: int, user2_id: int):
    """Mark a chat as ended"""
    chat_data.update_one(
        {
            '$or': [
                {'user1_id': user1_id, 'user2_id': user2_id, 'end_time': None},
                {'user1_id': user2_id, 'user2_id': user1_id, 'end_time': None}
            ]
        },
        {'$set': {'end_time': datetime.now()}}
    )
    return

# Chat Retrieval
async def get_chat_by_token(token: str):
    """Retrieve a chat session by its unique token"""
    return chat_data.find_one({'token': token})

# Statistics
async def full_userbase():
    user_docs = user_data.find()
    user_ids = []
    for doc in user_docs:
        user_ids.append(doc['_id'])
    return user_ids

async def del_user(user_id: int):
    user_data.delete_one({'_id': user_id})
    return

async def get_total_chats():
    return chat_data.count_documents({})

async def get_active_chats():
    return chat_data.count_documents({'end_time': None})

async def add_gupshup_user(user_id: int, telegram_username: str = None, telegram_first_name: str = None, telegram_photo_url: str = None):
    """Add or update a GUPSHUP user"""
    existing_user = gupshup_users.find_one({'_id': user_id})
    
    if not existing_user:
        gupshup_users.insert_one({
            '_id': user_id,
            'telegram_username': telegram_username or '',
            'telegram_first_name': telegram_first_name or '',
            'display_name': telegram_first_name or telegram_username or f"User{user_id}",
            'photo_url': telegram_photo_url or '',
            'created_at': datetime.now()
        })
    return

async def get_gupshup_user(user_id: int):
    """Get GUPSHUP user data"""
    return gupshup_users.find_one({'_id': user_id})

async def update_gupshup_profile(user_id: int, display_name: str = None, photo_url: str = None):
    """Update user's display name and/or photo"""
    update_data = {}
    if display_name is not None:
        update_data['display_name'] = display_name
    if photo_url is not None:
        update_data['photo_url'] = photo_url
    
    if update_data:
        gupshup_users.update_one({'_id': user_id}, {'$set': update_data})
    return

async def save_gupshup_message(message_data: dict):
    """Save a message to a group"""
    gupshup_messages.insert_one(message_data)
    return

async def get_group_messages(group_name: str, limit: int = 50):
    """Get recent messages from a group (auto-deletes messages older than 2 days)"""
    from datetime import timedelta
    
    two_days_ago = datetime.now() - timedelta(days=2)
    gupshup_messages.delete_many({'group': group_name, 'timestamp': {'$lt': two_days_ago}})
    
    messages = gupshup_messages.find({'group': group_name}).sort('timestamp', -1).limit(limit)
    
    result = []
    for msg in messages:
        user = await get_gupshup_user(msg['user_id'])
        result.append({
            'user_id': msg['user_id'],
            'user_name': user.get('display_name', 'Anonymous') if user else 'Anonymous',
            'user_photo': user.get('photo_url', '') if user else '',
            'text': msg.get('text', ''),
            'image_url': msg.get('image_url', ''),
            'gif_url': msg.get('gif_url', ''),
            'timestamp': msg['timestamp'].isoformat()
        })
    
    result.reverse()
    return result

async def get_active_users_in_group(group_name: str):
    """Get count of active users in a group"""
    return gupshup_messages.distinct('user_id', {'group': group_name})
