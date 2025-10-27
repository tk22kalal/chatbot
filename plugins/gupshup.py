from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from bot import Bot
from config import PORT
from database.database import add_gupshup_user
import os

@Bot.on_message(filters.command('group') & filters.private)
async def group_command(client: Bot, message: Message):
    """Handle /group command - show GUPSHUP button"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    photo_url = ""
    try:
        import os
        os.makedirs('static/uploads', exist_ok=True)
        
        photos = await client.get_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            photo = photos.photos[0]
            file_id = photo[-1].file_id
            destination = f"static/uploads/profile_{user_id}.jpg"
            downloaded_file = await client.download_media(file_id, file_name=destination)
            if downloaded_file and os.path.exists(downloaded_file):
                photo_url = f"/static/uploads/profile_{user_id}.jpg"
    except Exception as e:
        print(f"Failed to download profile photo: {e}")
    
    await add_gupshup_user(user_id, username, first_name, photo_url)
    
    webapp_url = os.environ.get("REPLIT_DEV_DOMAIN", "localhost")
    if not webapp_url.startswith("http"):
        webapp_url = f"https://{webapp_url}"
    
    webapp_info = WebAppInfo(url=webapp_url)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗣 GUPSHUP", web_app=webapp_info)]
    ])
    
    await message.reply_text(
        "🎉 <b>Welcome to GUPSHUP!</b>\n\n"
        "Click the button below to join group chats and connect with people!\n\n"
        "📚 Available Groups:\n"
        "• ENGINEER\n"
        "• CIVIL\n"
        "• DOCTOR\n"
        "• 12TH\n"
        "• 11TH\n"
        "• 10TH\n"
        "• 9TH\n"
        "• 8TH\n\n"
        "💬 Chat anonymously or with your profile. Have fun!",
        reply_markup=keyboard
    )
