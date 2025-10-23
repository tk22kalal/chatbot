#(©)CodeXBotz - Chat Log Retrieval

from pyrogram import Client, filters
from pyrogram.types import Message
from datetime import datetime
from io import BytesIO

from bot import Bot
from config import ADMINS
from database.database import get_chat_by_token, get_user

@Bot.on_message(filters.command('getchat') & filters.private & filters.user(ADMINS))
async def get_chat_command(client: Bot, message: Message):
    """
    Retrieve and send chat history as a .txt file
    Usage: /getchat TOKEN
    """
    # Check if token is provided
    if len(message.command) < 2:
        await message.reply_text(
            "❌ <b>Usage:</b> <code>/getchat TOKEN</code>\n\n"
            "Example: <code>/getchat ABC123XY</code>"
        )
        return
    
    token = message.command[1].upper().strip()
    
    # Show processing message
    processing_msg = await message.reply_text("🔍 Retrieving chat history...")
    
    # Retrieve chat from database
    chat = await get_chat_by_token(token)
    
    if not chat:
        await processing_msg.edit_text(
            f"❌ No chat found with token: <code>{token}</code>\n\n"
            "Please check the token and try again."
        )
        return
    
    # Get user details
    user1 = await get_user(chat['user1_id'])
    user2 = await get_user(chat['user2_id'])
    
    # Format chat log - Simple format as requested
    chat_log = f"Anonymous Chat Log - Token: {token}\n"
    chat_log += "-" * 39 + "\n"
    
    # User details
    chat_log += f"[User1: @{user1.get('username', 'N/A')} | ID: {chat['user1_id']} | Gender: {user1.get('gender', 'N/A')}]\n"
    chat_log += f"[User2: @{user2.get('username', 'N/A')} | ID: {chat['user2_id']} | Gender: {user2.get('gender', 'N/A')}]\n\n"
    
    # Messages - Simple one-line format
    messages = chat.get('messages', [])
    
    if not messages:
        chat_log += "(No messages in this chat)\n"
    else:
        for msg in messages:
            sender_id = msg.get('sender_id')
            timestamp = msg.get('timestamp', datetime.now())
            text = msg.get('text', '[Message]')
            
            # Determine which user sent the message
            if sender_id == chat['user1_id']:
                sender_label = "User1"
            else:
                sender_label = "User2"
            
            time_str = timestamp.strftime('%I:%M %p')
            # Single line format: [HH:MM AM/PM] UserX: message
            chat_log += f"[{time_str}] {sender_label}: {text}\n"
    
    # Create file in memory
    file_bytes = BytesIO(chat_log.encode('utf-8'))
    file_bytes.name = f"chat_{token}.txt"
    
    # Send file
    chat_status = 'Active' if not chat.get('end_time') else 'Ended'
    await message.reply_document(
        document=file_bytes,
        caption=f"📄 <b>Chat History</b>\n\n"
                f"Token: <code>{token}</code>\n"
                f"Messages: {len(messages)}\n"
                f"Status: {chat_status}"
    )
    
    # Delete processing message
    await processing_msg.delete()
