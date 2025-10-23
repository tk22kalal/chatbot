#(©)CodeXBotz - Anonymous Chat Handler
from config import ADMINS
import random
import time
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from pyrogram.enums import ChatAction
from pyrogram.enums import ParseMode
from bot import Bot
from config import PARTNER_FOUND_MSG, PARTNER_LEFT_MSG, SEARCHING_MSG, STOPPED_CHAT_MSG, CHANNEL_ID
from database.database import (
    get_user, set_user_searching, set_user_partner, 
    get_searching_users, clear_user_chat_state,
    log_chat_start, log_message, end_chat
)

async def try_match_users(client: Bot, user_id: int, user: dict):
    """Attempt to match a user with an available partner"""
    # Get all searching users (excluding current user)
    searching_users = await get_searching_users()
    available_users = [u for u in searching_users if u['_id'] != user_id]
    
    if available_users:
        # Random partner selection
        partner = random.choice(available_users)
        partner_id = partner['_id']
        
        # Connect both users
        await set_user_partner(user_id, partner_id)
        await set_user_partner(partner_id, user_id)
        await set_user_searching(user_id, False)
        await set_user_searching(partner_id, False)
        
        # Log chat start in database with unique token
        chat_token = await log_chat_start(user_id, partner_id)
        
        # Log to DB channel with token
        await client.send_to_channel(
            f"🔐 <b>New Chat Started</b>\n\n"
            f"<b>Token:</b> <code>{chat_token}</code>\n\n"
            f"<b>User1:</b> @{user.get('username', 'N/A')} (ID: {user_id}, Gender: {user.get('gender', 'N/A')})\n"
            f"<b>User2:</b> @{partner.get('username', 'N/A')} (ID: {partner_id}, Gender: {partner.get('gender', 'N/A')})"
        )
        
        # Notify both users
        chat_keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("/next"), KeyboardButton("/stop")]
        ], resize_keyboard=True)
        
        # Send to both users
        await client.send_message(user_id, PARTNER_FOUND_MSG, parse_mode="markdown", reply_markup=chat_keyboard)
        await client.send_message(partner_id, PARTNER_FOUND_MSG, parse_mode="markdown", reply_markup=chat_keyboard)
        
        return True
    return False

# Search for partner - /search command or "Find Partner" button
@Bot.on_message((filters.command('search') | filters.regex('^🔎 Find Partner$')) & filters.private & ~filters.user(ADMINS))
async def search_partner(client: Bot, message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    
    if not user:
        await message.reply_text("Please use /start first to set up your profile.")
        return
    
    if not user.get('gender'):
        await message.reply_text("Please use /start to select your gender first.")
        return
    
    # Check if user is already in a chat
    if user.get('partner_id'):
        await message.reply_text("You're already in a chat! Use /stop to end it or /next to find a new partner.")
        return
    
    # Check if user is already searching
    if user.get('searching'):
        await message.reply_text("You're already searching for a partner. Please wait...")
        return
    
    # Set user as searching
    await set_user_searching(user_id, True)
    
    # Try to find a match
    matched = await try_match_users(client, user_id, user)
    
    if not matched:
        # No partner available - user is now in queue
        await message.reply_text(SEARCHING_MSG)

# Stop current chat - /stop command
@Bot.on_message(filters.command('stop') & filters.private & ~filters.user(ADMINS))
async def stop_chat(client: Bot, message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    
    if not user:
        return
    
    partner_id = user.get('partner_id')
    
    if not partner_id:
        # Not in a chat
        if user.get('searching'):
            await set_user_searching(user_id, False)
            await message.reply_text("Search cancelled.")
        else:
            await message.reply_text("You're not in a chat right now. Use /search to find a partner.")
        return
    
    # End the chat
    await end_chat(user_id, partner_id)
    
    # Log to DB channel
    partner = await get_user(partner_id)
    await client.send_to_channel(
        f"❌ <b>Chat Ended</b>\n\n"
        f"User 1: {user_id} (@{user.get('username', 'N/A')})\n"
        f"User 2: {partner_id} (@{partner.get('username', 'N/A')})\n"
        f"Ended by: {user_id}"
    )
    
    # Clear chat state for both users
    await clear_user_chat_state(user_id)
    await clear_user_chat_state(partner_id)
    
    # Notify both users
    search_keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("🔎 Find Partner")]
    ], resize_keyboard=True)
    
    await message.reply_text(STOPPED_CHAT_MSG, reply_markup=search_keyboard)
    await client.send_message(partner_id, PARTNER_LEFT_MSG, reply_markup=search_keyboard)

# Next partner - /next command
@Bot.on_message(filters.command('next') & filters.private & ~filters.user(ADMINS))
async def next_partner(client: Bot, message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    
    if not user:
        return
    
    partner_id = user.get('partner_id')
    
    if not partner_id:
        await message.reply_text("You're not in a chat. Use /search to find a partner.")
        return
    
    # End current chat
    await end_chat(user_id, partner_id)
    
    # Log to DB channel
    partner = await get_user(partner_id)
    await client.send_to_channel(
        f"⏭ <b>User Skipped to Next</b>\n\n"
        f"User 1: {user_id} (@{user.get('username', 'N/A')})\n"
        f"User 2: {partner_id} (@{partner.get('username', 'N/A')})\n"
        f"Skipped by: {user_id}"
    )
    
    # Clear partner for both users
    await clear_user_chat_state(user_id)
    await clear_user_chat_state(partner_id)
    
    # Notify partner
    search_keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("🔎 Find Partner")]
    ], resize_keyboard=True)
    
    await client.send_message(partner_id, PARTNER_LEFT_MSG, reply_markup=search_keyboard)
    
    # Automatically search for new partner for current user
    await set_user_searching(user_id, True)
    
    matched = await try_match_users(client, user_id, user)
    
    if not matched:
        await message.reply_text(SEARCHING_MSG)

# Handle all messages (forward to partner) - ANONYMOUSLY
@Bot.on_message(filters.private & ~filters.command(['start', 'search', 'next', 'stop', 'users']) & ~filters.user(ADMINS))
async def handle_messages(client: Bot, message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    
    if not user:
        return
    
    partner_id = user.get('partner_id')
    
    if not partner_id:
        # User is not in a chat
        if not user.get('searching'):
            await message.reply_text("❌ You're not in a chat. Use /search to find a partner!")
        return
    
    # Forward message to partner ANONYMOUSLY
    try:
        # Send typing action
        await client.send_chat_action(partner_id, ChatAction.TYPING)
        
        # Forward message anonymously by reconstructing it without metadata
        if message.text:
            # Text message
            await client.send_message(partner_id, message.text)
        elif message.photo:
            # Photo message
            await client.send_photo(partner_id, message.photo.file_id, caption=message.caption or "")
        elif message.video:
            # Video message
            await client.send_video(partner_id, message.video.file_id, caption=message.caption or "")
        elif message.audio:
            # Audio message
            await client.send_audio(partner_id, message.audio.file_id, caption=message.caption or "")
        elif message.voice:
            # Voice message
            await client.send_voice(partner_id, message.voice.file_id, caption=message.caption or "")
        elif message.document:
            # Document message
            await client.send_document(partner_id, message.document.file_id, caption=message.caption or "")
        elif message.sticker:
            # Sticker
            await client.send_sticker(partner_id, message.sticker.file_id)
        elif message.animation:
            # GIF/Animation
            await client.send_animation(partner_id, message.animation.file_id, caption=message.caption or "")
        elif message.video_note:
            # Video note (round video)
            await client.send_video_note(partner_id, message.video_note.file_id)
        else:
            # Unsupported message type
            await message.reply_text("❌ This message type is not supported.")
            return
        
        # Log message in database
        message_text = message.text or message.caption or "[Media]"
        await log_message(user_id, partner_id, user_id, message_text)
        
        # Log to DB channel (sample only, not all messages to avoid spam)
        # Only log every 10th message to reduce channel spam
        if random.randint(1, 10) == 1:  # 10% sampling
            partner = await get_user(partner_id)
            log_text = f"💬 <b>Message Sample</b>\n\n"
            log_text += f"From: {user_id} (@{user.get('username', 'N/A')})\n"
            log_text += f"To: {partner_id} (@{partner.get('username', 'N/A')})\n"
            log_text += f"Type: {message.media or 'text'}"
            
            await client.send_to_channel(log_text)
            
    except Exception as e:
        # Partner might have blocked the bot or chat ended
        await message.reply_text("❌ Failed to send message. Your partner may have left. Use /search to find a new partner.")
        await clear_user_chat_state(user_id)
        if partner_id:
            await clear_user_chat_state(partner_id)
