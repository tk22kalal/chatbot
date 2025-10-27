#(©)CodeXBotz - Modified for Anonymous Chat Bot

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, WebAppInfo
import os

from bot import Bot
from config import ADMINS, START_MSG
from database.database import add_user, present_user, get_user, update_user_gender, full_userbase, get_total_chats, get_active_chats

# Start Command - Ask for gender if new user
@Bot.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Check if user exists
    if not await present_user(user_id):
        # New user - add to database
        await add_user(user_id, username, first_name)
    
    # Get user data
    user = await get_user(user_id)
    
    # If user hasn't selected gender, ask for it
    if not user or user.get('gender') is None:
        gender_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👦 Male", callback_data="gender_male"),
                InlineKeyboardButton("👧 Female", callback_data="gender_female")
            ]
        ])
        
        await message.reply_text(
            START_MSG,
            reply_markup=gender_keyboard
        )
    else:
        # User already has gender - show search keyboard with GUPSHUP
        webapp_url = os.environ.get("WEB_URL") or os.environ.get("REPLIT_DEV_DOMAIN")
        if webapp_url and not webapp_url.startswith("http"):
            webapp_url = f"https://{webapp_url}"
        
        if webapp_url:
            search_keyboard = ReplyKeyboardMarkup([
                [KeyboardButton("🔎 Find Partner"), KeyboardButton("🗣 GUPSHUP", web_app=WebAppInfo(url=webapp_url))]
            ], resize_keyboard=True)
        else:
            search_keyboard = ReplyKeyboardMarkup([
                [KeyboardButton("🔎 Find Partner")]
            ], resize_keyboard=True)
        
        await message.reply_text(
            f"Welcome back! Ready to chat anonymously?\n\nYour gender: {user['gender'].title()}\n\nClick 'Find Partner' or use /search to start chatting!",
            reply_markup=search_keyboard
        )

# Handle gender selection
@Bot.on_callback_query(filters.regex("^gender_"))
async def gender_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    gender = callback_query.data.split("_")[1]  # male or female
    
    # Update user gender in database
    await update_user_gender(user_id, gender)
    
    # Show search keyboard with GUPSHUP
    webapp_url = os.environ.get("WEB_URL") or os.environ.get("REPLIT_DEV_DOMAIN")
    if webapp_url and not webapp_url.startswith("http"):
        webapp_url = f"https://{webapp_url}"
    
    if webapp_url:
        search_keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("🔎 Find Partner"), KeyboardButton("🗣 GUPSHUP", web_app=WebAppInfo(url=webapp_url))]
        ], resize_keyboard=True)
    else:
        search_keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("🔎 Find Partner")]
        ], resize_keyboard=True)
    
    await callback_query.message.edit_text(
        f"✅ Gender set to: {gender.title()}\n\nNow click 'Find Partner' or use /search to start chatting anonymously!",
        reply_markup=None
    )
    
    await callback_query.message.reply_text(
        "Ready to find a chat partner?",
        reply_markup=search_keyboard
    )
    
    await callback_query.answer()

# Stats command (Admin only)
@Bot.on_message(filters.command('users') & filters.private & filters.user(ADMINS))
async def get_users_stats(client: Bot, message: Message):
    users = await full_userbase()
    total_chats = await get_total_chats()
    active_chats = await get_active_chats()
    
    stats_text = f"""📊 <b>Bot Statistics</b>

👥 Total Users: <code>{len(users)}</code>
💬 Total Chats: <code>{total_chats}</code>
🟢 Active Chats: <code>{active_chats}</code>"""
    
    await message.reply_text(stats_text)

# About callback
@Bot.on_callback_query(filters.regex("^about$"))
async def about_callback(client: Client, callback_query: CallbackQuery):
    about_text = """<b>About Anonymous Chat Bot</b>

This bot allows you to chat anonymously with random strangers on Telegram.

<b>Commands:</b>
/start - Start the bot
/search - Find a chat partner
/next - Find new partner
/stop - Stop current chat

Made with ❤️"""
    
    await callback_query.message.edit_text(about_text)
    await callback_query.answer()

# Close callback
@Bot.on_callback_query(filters.regex("^close$"))
async def close_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.message.delete()
    await callback_query.answer()
