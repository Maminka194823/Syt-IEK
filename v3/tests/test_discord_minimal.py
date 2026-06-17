"""Minimal Discord bot test to isolate the issue."""
import discord
import os
from dotenv import load_dotenv

load_dotenv()

# Simple bot test
intents = discord.Intents.default()
intents.message_content = True

class MinimalBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
    
    async def on_ready(self):
        print(f'Logged in as {self.user}')
        print('Minimal bot is ready!')
    
    async def on_message(self, message):
        if message.author == self.user:
            return
        
        if self.user in message.mentions:
            await message.reply("heya pookie! 😊 minimal bot working girll! ✈️")

def main():
    bot_token = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('DISCORD_TOKEN')
    
    if not bot_token:
        print("  No Discord token found")
        return
    
    print("🧪 Testing minimal Discord bot...")
    bot = MinimalBot()
    
    try:
        bot.run(bot_token)
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()