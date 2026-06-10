#(©)CodeXBotz - Anonymous Chat Handler + AI Girl
import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from pyrogram.enums import ChatAction, ParseMode
import os

from bot import Bot
from config import PARTNER_FOUND_MSG, PARTNER_LEFT_MSG, SEARCHING_MSG, STOPPED_CHAT_MSG, CHANNEL_ID, AI_GIRL_SKIP_THRESHOLD
from database.database import (
    get_user, set_user_searching, set_user_partner,
    get_searching_users, clear_user_chat_state,
    log_chat_start, log_message, end_chat,
    # AI girl
    AI_GIRL_PARTNER_ID, set_user_ai_partner, clear_user_ai_partner,
    get_ai_history, set_ai_history, increment_user_msg_count,
    record_chat_end_and_get_skips, get_skip_count, reset_skip_count,
)
from plugins.ai_girl import handle_ai_message, clear_session_cache


def _get_webapp_url() -> str | None:
    url = (os.environ.get("WEB_URL") or os.environ.get("REPLIT_DEV_DOMAIN") or "").strip().rstrip("/")
    if not url:
        return None
    if not url.startswith("http"):
        url = f"https://{url}"
    return url


def _chat_keyboard(webapp_url: str | None) -> ReplyKeyboardMarkup:
    if webapp_url:
        return ReplyKeyboardMarkup([
            [KeyboardButton("/next"), KeyboardButton("/stop")],
            [KeyboardButton("🗣 GUPSHUP", web_app=WebAppInfo(url=webapp_url))]
        ], resize_keyboard=True)
    return ReplyKeyboardMarkup([[KeyboardButton("/next"), KeyboardButton("/stop")]], resize_keyboard=True)


def _search_keyboard(webapp_url: str | None) -> ReplyKeyboardMarkup:
    if webapp_url:
        return ReplyKeyboardMarkup([
            [KeyboardButton("🔎 Find Partner"), KeyboardButton("🗣 GUPSHUP", web_app=WebAppInfo(url=webapp_url))]
        ], resize_keyboard=True)
    return ReplyKeyboardMarkup([[KeyboardButton("🔎 Find Partner")]], resize_keyboard=True)


# ── AI Girl connector ─────────────────────────────────────────────────────────

async def _start_ai_chat(client: Bot, user_id: int) -> None:
    """Silently connect user to AI girl — feels identical to a real match."""
    await set_user_ai_partner(user_id)
    webapp_url = _get_webapp_url()
    await client.send_message(
        user_id,
        PARTNER_FOUND_MSG,
        parse_mode=ParseMode.HTML,
        reply_markup=_chat_keyboard(webapp_url)
    )


# ── Match users OR fall back to AI ───────────────────────────────────────────

async def try_match_users(client: Bot, user_id: int, user: dict) -> bool:
    """
    Try to find a real partner.
    If none found and user has hit the skip threshold → connect to AI girl.
    Returns True if matched (real or AI), False if queued.
    """
    searching_users   = await get_searching_users()
    available_users   = [u for u in searching_users if u['_id'] != user_id]

    if available_users:
        partner       = random.choice(available_users)
        partner_id    = partner['_id']

        await set_user_partner(user_id, partner_id)
        await set_user_partner(partner_id, user_id)
        await set_user_searching(user_id, False)
        await set_user_searching(partner_id, False)
        await reset_skip_count(user_id)

        chat_token = await log_chat_start(user_id, partner_id)

        await client.send_to_channel(
            f"🔐 <b>New Chat Started</b>\n\n"
            f"<b>Token:</b> <code>{chat_token}</code>\n\n"
            f"<b>User1:</b> @{user.get('username', 'N/A')} (ID: {user_id})\n"
            f"<b>User2:</b> @{partner.get('username', 'N/A')} (ID: {partner_id})"
        )

        webapp_url    = _get_webapp_url()
        chat_kb       = _chat_keyboard(webapp_url)
        await client.send_message(user_id,    PARTNER_FOUND_MSG, parse_mode=ParseMode.HTML, reply_markup=chat_kb)
        await client.send_message(partner_id, PARTNER_FOUND_MSG, parse_mode=ParseMode.HTML, reply_markup=chat_kb)
        return True

    # No real partner available
    skip_count = await get_skip_count(user_id)
    no_one_else = len(available_users) == 0  # user is alone in the whole bot

    if no_one_else or skip_count >= AI_GIRL_SKIP_THRESHOLD:
        # Reset skip count NOW so after AI girl the next /next → real user search
        await reset_skip_count(user_id)
        await _start_ai_chat(client, user_id)
        return True   # "matched" (to AI)

    return False   # still queued


# ── /search ───────────────────────────────────────────────────────────────────

@Bot.on_message((filters.command('search') | filters.regex('^🔎 Find Partner$')) & filters.private)
async def search_partner(client: Bot, message: Message):
    user_id = message.from_user.id
    user    = await get_user(user_id)

    if not user:
        await message.reply_text("Please use /start first.")
        return
    if not user.get('gender'):
        await message.reply_text("Please use /start to set your gender first.")
        return
    if user.get('partner_id') == AI_GIRL_PARTNER_ID or user.get('ai_partner'):
        await message.reply_text("You're in a chat! Use /stop to end it or /next for a new partner.")
        return
    if user.get('partner_id'):
        await message.reply_text("You're already in a chat! Use /stop to end it.")
        return
    if user.get('searching'):
        await message.reply_text("Already searching… please wait ⏳")
        return

    await set_user_searching(user_id, True)
    matched = await try_match_users(client, user_id, user)

    if not matched:
        await message.reply_text(SEARCHING_MSG, reply_markup=_search_keyboard(_get_webapp_url()))


# ── /stop ─────────────────────────────────────────────────────────────────────

@Bot.on_message(filters.command('stop') & filters.private)
async def stop_chat(client: Bot, message: Message):
    user_id = message.from_user.id
    user    = await get_user(user_id)
    if not user:
        return

    # ── AI girl session ───────────────────────────────────────────────────────
    if user.get('ai_partner') or user.get('partner_id') == AI_GIRL_PARTNER_ID:
        clear_session_cache(user_id)
        await clear_user_ai_partner(user_id)
        await message.reply_text(
            STOPPED_CHAT_MSG,
            reply_markup=_search_keyboard(_get_webapp_url())
        )
        return

    partner_id = user.get('partner_id')

    if not partner_id:
        if user.get('searching'):
            await set_user_searching(user_id, False)
            await message.reply_text("Search cancelled.")
        else:
            await message.reply_text("You're not in a chat. Use /search to find a partner.")
        return

    # Record msg count for skip tracking
    await record_chat_end_and_get_skips(user_id)
    await end_chat(user_id, partner_id)

    partner = await get_user(partner_id)
    await client.send_to_channel(
        f"❌ <b>Chat Ended</b>\n\n"
        f"User 1: {user_id} | User 2: {partner_id}\nEnded by: {user_id}"
    )

    await clear_user_chat_state(user_id)
    await clear_user_chat_state(partner_id)

    search_kb = _search_keyboard(_get_webapp_url())
    await message.reply_text(STOPPED_CHAT_MSG, reply_markup=search_kb)
    await client.send_message(partner_id, PARTNER_LEFT_MSG, reply_markup=search_kb)


# ── /next ─────────────────────────────────────────────────────────────────────

@Bot.on_message(filters.command('next') & filters.private)
async def next_partner(client: Bot, message: Message):
    user_id = message.from_user.id
    user    = await get_user(user_id)
    if not user:
        return

    # ── Leave AI girl session ─────────────────────────────────────────────────
    if user.get('ai_partner') or user.get('partner_id') == AI_GIRL_PARTNER_ID:
        clear_session_cache(user_id)
        await clear_user_ai_partner(user_id)
        # Count AI chat as a "skip" (short chat) so counter doesn't reset
        skip_count = await get_skip_count(user_id)
        # immediately try to find a real partner
        user_fresh = await get_user(user_id)
        await set_user_searching(user_id, True)
        matched = await try_match_users(client, user_id, user_fresh or user)
        if not matched:
            await message.reply_text(SEARCHING_MSG, reply_markup=_search_keyboard(_get_webapp_url()))
        return

    partner_id = user.get('partner_id')
    if not partner_id:
        await message.reply_text("You're not in a chat. Use /search to find a partner.")
        return

    # Record skip count for real chats
    new_skips = await record_chat_end_and_get_skips(user_id)
    await end_chat(user_id, partner_id)

    partner = await get_user(partner_id)
    await client.send_to_channel(
        f"⏭ <b>User Skipped</b>\n\nUser 1: {user_id} | User 2: {partner_id}\nSkipped by: {user_id}"
    )

    await clear_user_chat_state(user_id)
    await clear_user_chat_state(partner_id)

    # Notify partner
    await client.send_message(partner_id, PARTNER_LEFT_MSG, reply_markup=_search_keyboard(_get_webapp_url()))

    # Auto-search for current user
    await set_user_searching(user_id, True)
    user_fresh = await get_user(user_id)
    matched = await try_match_users(client, user_id, user_fresh or user)
    if not matched:
        await message.reply_text(SEARCHING_MSG)


# ── Message forwarder (real chat OR AI girl) ──────────────────────────────────

@Bot.on_message(
    filters.private
    & ~filters.command(['start', 'search', 'next', 'stop', 'users',
                        'group', 'gupshup', 'broadcast', 'stats', 'getchat'])
)
async def handle_messages(client: Bot, message: Message):
    user_id = message.from_user.id
    user    = await get_user(user_id)
    if not user:
        return

    # ── Route to AI girl ──────────────────────────────────────────────────────
    if user.get('ai_partner') or user.get('partner_id') == AI_GIRL_PARTNER_ID:
        asyncio.ensure_future(
            handle_ai_message(
                client, message, user_id,
                get_ai_history_fn   = get_ai_history,
                set_ai_history_fn   = set_ai_history,
                increment_msg_fn    = increment_user_msg_count,
            )
        )
        return

    # ── Route to real partner ─────────────────────────────────────────────────
    partner_id = user.get('partner_id')
    if not partner_id:
        if not user.get('searching'):
            await message.reply_text("❌ You're not in a chat. Use /search to find a partner!")
        return

    # Increment message count for skip-threshold tracking
    await increment_user_msg_count(user_id)

    try:
        await client.send_chat_action(partner_id, ChatAction.TYPING)

        if message.text:
            await client.send_message(partner_id, message.text)
        elif message.photo:
            await client.send_photo(partner_id, message.photo.file_id, caption=message.caption or "")
        elif message.video:
            await client.send_video(partner_id, message.video.file_id, caption=message.caption or "")
        elif message.audio:
            await client.send_audio(partner_id, message.audio.file_id, caption=message.caption or "")
        elif message.voice:
            await client.send_voice(partner_id, message.voice.file_id, caption=message.caption or "")
        elif message.document:
            await client.send_document(partner_id, message.document.file_id, caption=message.caption or "")
        elif message.sticker:
            await client.send_sticker(partner_id, message.sticker.file_id)
        elif message.animation:
            await client.send_animation(partner_id, message.animation.file_id, caption=message.caption or "")
        elif message.video_note:
            await client.send_video_note(partner_id, message.video_note.file_id)
        else:
            await message.reply_text("❌ This message type is not supported.")
            return

        msg_text = message.text or message.caption or "[Media]"
        await log_message(user_id, partner_id, user_id, msg_text)

        if random.randint(1, 10) == 1:
            partner = await get_user(partner_id)
            await client.send_to_channel(
                f"💬 <b>Message Sample</b>\n\n"
                f"From: {user_id} (@{user.get('username', 'N/A')})\n"
                f"To: {partner_id} (@{(partner or {}).get('username', 'N/A')})\n"
                f"Type: {message.media or 'text'}"
            )

    except Exception as e:
        await message.reply_text("❌ Failed to send. Your partner may have left. Use /search.")
        await clear_user_chat_state(user_id)
        if partner_id:
            await clear_user_chat_state(partner_id)
