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
        self.channel_accessible = False

    async def start(self):
        await super().start()
        usr_bot_me = await self.get_me()
        self.uptime = datetime.now()

        # Verify DB Channel access
        if CHANNEL_ID != 0:
            try:
                db_channel = await self.get_chat(CHANNEL_ID)
                self.db_channel = db_channel
                
                # Try to resolve peer by getting chat member
                try:
                    bot_member = await self.get_chat_member(CHANNEL_ID, "me")
                    self.LOGGER(__name__).info(f"Bot status in channel: {bot_member.status}")
                except:
                    pass
                
                test = await self.send_message(chat_id=CHANNEL_ID, text="✅ Anonymous Chat Bot Started - Logging Channel Active")
                await test.delete()
                self.channel_accessible = True
                self.LOGGER(__name__).info(f"✅ Successfully connected to logging channel: {db_channel.title}")
            except Exception as e:
                self.LOGGER(__name__).error(f"❌ Failed to access channel {CHANNEL_ID}: {e}")
                self.LOGGER(__name__).warning("Make sure:")
                self.LOGGER(__name__).warning("1. The bot is added to the channel")
                self.LOGGER(__name__).warning("2. The bot has admin rights with 'Post Messages' permission")
                self.LOGGER(__name__).warning("3. The CHANNEL_ID is correct (should be like -100xxxxxxxxx)")
                self.LOGGER(__name__).info("Bot will continue but logging to channel is disabled.")
                self.channel_accessible = False
        else:
            self.LOGGER(__name__).info("CHANNEL_ID is 0, logging to channel is disabled.")
            self.channel_accessible = False

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
    
    async def send_to_channel(self, text: str):
        """Helper method to safely send messages to the logging channel"""
        if not self.channel_accessible or CHANNEL_ID == 0:
            return False
        
        try:
            await self.send_message(CHANNEL_ID, text)
            return True
        except Exception as e:
            self.LOGGER(__name__).error(f"Failed to send to channel: {e}")
            return False

    async def stop(self, *args):
        await super().stop()
        self.LOGGER(__name__).info("Bot stopped.")
