#(©)CodeXBotz - Modified for Anonymous Chat

import pymongo
import os
from config import DB_URI, DB_NAME
from datetime import datetime

dbclient = pymongo.MongoClient(DB_URI)
database = dbclient[DB_NAME]

user_data = database['users']
chat_data = database['chats']

# User Management
async def present_user(user_id: int):
    found = user_data.find_one({'_id': user_id})
    return bool(found)

async def add_user(user_id: int, username: str = None, first_name: str = None):
    user_data.insert_one({
        '_id': user_id,
        'username': username,
        'first_name': first_name,
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
    user_data.update_one({'_id': user_id}, {'$set': {'partner_id': partner_id}})
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
    """Log when a chat starts between two users"""
    chat_data.insert_one({
        'user1_id': user1_id,
        'user2_id': user2_id,
        'start_time': datetime.now(),
        'end_time': None,
        'messages': []
    })
    return

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
