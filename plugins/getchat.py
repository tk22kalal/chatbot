#(©)CodeXBotz - Chat Log Retrieval (supports real chats + AI girl chats)

from pyrogram import Client, filters
from pyrogram.types import Message
from datetime import datetime
from io import BytesIO

from bot import Bot
from config import ADMINS
from database.database import get_chat_by_token, get_user, AI_GIRL_PARTNER_ID

@Bot.on_message(filters.command('getchat') & filters.private & filters.user(ADMINS))
async def get_chat_command(client: Bot, message: Message):
    """
    Retrieve and send chat history as a .txt file.
    Works for real user chats AND AI girl chats.
    Usage: /getchat TOKEN
    """
    if len(message.command) < 2:
        await message.reply_text(
            "❌ <b>Usage:</b> <code>/getchat TOKEN</code>\n\n"
            "Example: <code>/getchat ABC123XY</code>"
        )
        return

    token = message.command[1].upper().strip()
    processing_msg = await message.reply_text("🔍 Retrieving chat history...")

    chat = await get_chat_by_token(token)

    if not chat:
        await processing_msg.edit_text(
            f"❌ No chat found with token: <code>{token}</code>\n\n"
            "Please check the token and try again."
        )
        return

    user1_id = chat['user1_id']
    user2_id = chat['user2_id']

    user1 = await get_user(user1_id)
    is_ai_chat = (user2_id == AI_GIRL_PARTNER_ID)

    # ── Build header ──────────────────────────────────────────────────────────
    chat_log  = f"Chat Log — Token: {token}\n"
    chat_log += "-" * 39 + "\n"

    u1_name   = user1.get('username', 'N/A') if user1 else 'N/A'
    u1_gender = user1.get('gender', 'N/A')   if user1 else 'N/A'
    chat_log += f"[User:    @{u1_name} | ID: {user1_id} | Gender: {u1_gender}]\n"

    if is_ai_chat:
        chat_log += "[Partner: AI Girl (bot)]\n\n"
    else:
        user2     = await get_user(user2_id)
        u2_name   = user2.get('username', 'N/A') if user2 else 'N/A'
        u2_gender = user2.get('gender', 'N/A')   if user2 else 'N/A'
        chat_log += f"[Partner: @{u2_name} | ID: {user2_id} | Gender: {u2_gender}]\n\n"

    # ── Messages ──────────────────────────────────────────────────────────────
    messages = chat.get('messages', [])

    if not messages:
        chat_log += "(No messages in this chat)\n"
    else:
        for msg in messages:
            sender_id = msg.get('sender_id')
            timestamp = msg.get('timestamp', datetime.now())
            text      = msg.get('text', '[Message]')
            time_str  = timestamp.strftime('%I:%M %p')

            if sender_id == user1_id:
                label = "User"
            elif sender_id == AI_GIRL_PARTNER_ID:
                label = "AI Girl"
            else:
                label = "Partner"

            chat_log += f"[{time_str}] {label}: {text}\n"

    # ── Send file ─────────────────────────────────────────────────────────────
    file_bytes      = BytesIO(chat_log.encode('utf-8'))
    file_bytes.name = f"chat_{token}.txt"
    chat_status     = 'Active' if not chat.get('end_time') else 'Ended'
    chat_type       = 'AI Girl Chat' if is_ai_chat else 'Anonymous Chat'

    await message.reply_document(
        document=file_bytes,
        caption=(
            f"📄 <b>Chat History</b>\n\n"
            f"Type:     {chat_type}\n"
            f"Token:    <code>{token}</code>\n"
            f"Messages: {len(messages)}\n"
            f"Status:   {chat_status}"
        )
    )
    await processing_msg.delete()
