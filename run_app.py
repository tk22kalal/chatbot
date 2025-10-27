import asyncio
from bot import Bot
from webserver import create_app
from aiohttp import web
from config import PORT

async def main():
    """Run both the bot and web server in the same event loop"""
    from config import TG_BOT_TOKEN, APP_ID, API_HASH
    
    app = await create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(PORT))
    await site.start()
    print(f"✅ Web server started on port {PORT}")
    print(f"🌐 GUPSHUP web interface is now accessible")
    
    if TG_BOT_TOKEN and APP_ID and API_HASH and TG_BOT_TOKEN != "" and APP_ID != 0:
        try:
            bot = Bot()
            await bot.start()
            print("✅ Telegram bot started successfully")
        except Exception as e:
            print(f"⚠️ Failed to start Telegram bot: {e}")
            print("📱 The web interface will still work without the bot")
    else:
        print("ℹ️ Telegram credentials not configured - bot will not start")
        print("📝 Configure TG_BOT_TOKEN, APP_ID, and API_HASH to enable the Telegram bot")
        print("🌐 Web server is running - you can test GUPSHUP at the URL above")
    
    await asyncio.Event().wait()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
