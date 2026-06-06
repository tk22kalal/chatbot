from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from bot import Bot
from database.database import add_gupshup_user
import os


def _build_webapp_url() -> str | None:
    """Return a clean https:// webapp URL from env, or None if not configured."""
    url = os.environ.get("WEB_URL") or os.environ.get("REPLIT_DEV_DOMAIN") or ""
    url = url.strip().rstrip("/")
    if not url:
        return None
    if not url.startswith("http"):
        url = f"https://{url}"
    return url


async def _get_photo_url(client: Bot, user_id: int, webapp_url: str) -> str:
    """
    Download the user's Telegram profile photo to the static folder and
    return an *absolute* URL so it works from any domain.
    Falls back to "" on any error.
    """
    try:
        os.makedirs("static/uploads", exist_ok=True)
        user_profile = await client.get_chat(user_id)
        if not (user_profile and user_profile.photo):
            return ""
        destination = f"static/uploads/profile_{user_id}.jpg"
        # Use the Chat object directly — more reliable than raw file_id string
        downloaded = await client.download_media(user_profile.photo.big_file_id, file_name=destination)
        if downloaded and os.path.exists(downloaded):
            # Return absolute URL so it works cross-origin in Telegram WebView
            return f"{webapp_url}/static/uploads/profile_{user_id}.jpg"
    except Exception as e:
        print(f"[gupshup] Could not download profile photo for {user_id}: {e}")
    return ""


@Bot.on_message(filters.command(["group", "gupshup"]) & filters.private)
async def group_command(client: Bot, message: Message):
    """Handle /group or /gupshup command — show GUPSHUP web-app button."""
    user_id    = message.from_user.id
    username   = message.from_user.username   or ""
    first_name = message.from_user.first_name or ""

    webapp_url = _build_webapp_url()

    if not webapp_url:
        await message.reply_text(
            "⚠️ <b>Web interface not configured</b>\n\n"
            "Set the <code>WEB_URL</code> environment variable to your server URL.\n"
            "Example: <code>https://chat.example.com</code>",
            parse_mode="HTML",
        )
        return

    # Download profile photo (absolute URL stored so the webapp can display it)
    photo_url = await _get_photo_url(client, user_id, webapp_url)
    await add_gupshup_user(user_id, username, first_name, photo_url)

    # Build keyboard — both inline and reply variants so user sees GUPSHUP button
    webapp_info = WebAppInfo(url=webapp_url)
    inline_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗣 Open GUPSHUP", web_app=webapp_info)]
    ])
    reply_kb = ReplyKeyboardMarkup([
        [KeyboardButton("🔎 Find Partner"), KeyboardButton("🗣 GUPSHUP", web_app=webapp_info)]
    ], resize_keyboard=True)

    await message.reply_text(
        "🎉 <b>Welcome to GUPSHUP!</b>\n\n"
        "Tap the button below to join group chats!\n\n"
        "📚 <b>Available Groups:</b>\n"
        "• 👨‍💻 ENGINEER  • 🏗️ CIVIL\n"
        "• ⚕️ DOCTOR    • 📚 12TH\n"
        "• 📖 11TH      • 📝 10TH\n"
        "• ✏️ 9TH       • 📓 8TH\n\n"
        "💬 Chat anonymously and have fun!",
        parse_mode="HTML",
        reply_markup=inline_kb,
    )
    # Also set the persistent reply keyboard
    await message.reply_text("Keyboard updated ✓", reply_markup=reply_kb)
