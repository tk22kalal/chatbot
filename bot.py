#(©)Codexbotz - Modified for Anonymous Chat Bot

import pyromod.listen
from pyrogram import Client
from pyrogram.enums import ParseMode
import sys
from datetime import datetime

from config import API_HASH, APP_ID, LOGGER, TG_BOT_TOKEN, TG_BOT_WORKERS, CHANNEL_ID

class Bot(Client):
    def __init__(self):
        super().__init__(
            name="AnonChatBot",
            api_hash=API_HASH,
            api_id=APP_ID,
            plugins={
                "root": "plugins"
            },
            workers=TG_BOT_WORKERS,
            bot_token=TG_BOT_TOKEN
        )
        self.LOGGER = LOGGER

    async def start(self):
        await super().start()
        usr_bot_me = await self.get_me()
        self.uptime = datetime.now()

        # Verify DB Channel access
        try:
            db_channel = await self.get_chat(CHANNEL_ID)
            self.db_channel = db_channel
            test = await self.send_message(chat_id=db_channel.id, text="✅ Anonymous Chat Bot Started - Logging Channel Active")
            await test.delete()
        except Exception as e:
            self.LOGGER(__name__).warning(e)
            self.LOGGER(__name__).warning(f"Make sure bot is Admin in DB Channel for logging. Current CHANNEL_ID: {CHANNEL_ID}")
            self.LOGGER(__name__).info("\nBot will continue but logging may not work.")

        self.set_parse_mode(ParseMode.HTML)
        self.LOGGER(__name__).info(f"Anonymous Chat Bot Running..!\n\nBot Username: @{usr_bot_me.username}")
        self.LOGGER(__name__).info(f""" \n\n       
░█████╗░███╗░░██╗░█████╗░███╗░░██╗  ░█████╗░██╗░░██╗░█████╗░████████╗
██╔══██╗████╗░██║██╔══██╗████╗░██║  ██╔══██╗██║░░██║██╔══██╗╚══██╔══╝
███████║██╔██╗██║██║░░██║██╔██╗██║  ██║░░╚═╝███████║███████║░░░██║░░░
██╔══██║██║╚████║██║░░██║██║╚████║  ██║░░██╗██╔══██║██╔══██║░░░██║░░░
██║░░██║██║░╚███║╚█████╔╝██║░╚███║  ╚█████╔╝██║░░██║██║░░██║░░░██║░░░
╚═╝░░╚═╝╚═╝░░╚══╝░╚════╝░╚═╝░░╚══╝  ░╚════╝░╚═╝░░╚═╝╚═╝░░╚═╝░░░╚═╝░░░
                                          """)
        self.username = usr_bot_me.username

    async def stop(self, *args):
        await super().stop()
        self.LOGGER(__name__).info("Bot stopped.")
