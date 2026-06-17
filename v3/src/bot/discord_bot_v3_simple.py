"""Aviation Girl V3 Discord Bot - Simplified Version."""
import discord
import sys
import os
import asyncio
from pathlib import Path

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent))

from memory.fast_memory import FastMemory
from rag.wikipedia_rag import WikipediaRAG

# Bot configuration
INTENTS = discord.Intents.default()
INTENTS.message_content = True

class AviationGirlV3Simple(discord.Client):
    """Aviation Girl V3 - Simplified version without model loading issues."""
    
    def __init__(self, bot_token: str):
        super().__init__(intents=INTENTS)
        self.bot_token = bot_token
        
        # Initialize systems
        self.memory = FastMemory("user_memory.json")
        self.rag = WikipediaRAG(max_context_length=500)
        
        print("  Memory system initialized")
        print("  RAG system initialized")
        print("⚠️ Model loading disabled for testing")

    async def on_ready(self):
        """Called when bot is ready."""
        print("\n" + "─" * 60)
        print("  Aviation Girl V3 - Simple Version Ready!")
        print("─" * 60)
        print(f'  Logged in as: {self.user}')
        print(f'  Bot ID: {self.user.id}')
        print("\n    Memory system ready!")
        print("    Wikipedia RAG ready!")
        print("  ⚠️ Using mock responses (no 7B model)")
        print("    Aviation Girl V3 is ready to fly!")
        print("─" * 60 + "\n")
    
    async def on_message(self, message):
        """Handle incoming messages."""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if bot was mentioned or replied to
        bot_mentioned = self.user in message.mentions
        bot_replied_to = message.reference and message.reference.resolved and message.reference.resolved.author == self.user
        
        if bot_mentioned or bot_replied_to:
            # Show typing indicator
            async with message.channel.typing():
                # Process message with V3 features
                response = await self.process_message_v3(message)
                await message.reply(response)
    
    async def process_message_v3(self, message):
        """Process message with V3 features (memory + RAG + mock responses)"""
        user_id = str(message.author.id)
        user_message = message.content.replace(f'<@{self.user.id}>', '').strip()
        
        try:
            # Auto-detect and store memories
            self.memory.auto_detect(user_id, user_message)
            
            # Get memory context
            memory_context = self.memory.get_context(user_id)
            
            # Try RAG retrieval
            rag_result = None
            rag_context = ""
            
            try:
                if self.rag.should_use_rag(user_message):
                    rag_result = self.rag.retrieve(user_message)
                    if rag_result:
                        rag_context = self.rag.format_context(rag_result)
            except Exception as e:
                print(f"RAG error: {e}")
                # Continue without RAG
            
            # Generate mock response based on context
            response = self.generate_mock_response(user_message, memory_context, rag_result)
            
            # Add source citation if RAG was used
            if rag_result:
                response += f"\n\n*Source: [Wikipedia]({rag_result['url']})*"
            
            return response
            
        except Exception as e:
            print(f"Error processing message: {e}")
            return "sorry pookie! 😊 something went wrong girll! ✈️"
    
    def generate_mock_response(self, message: str, memory_context: str, rag_result: dict) -> str:
        """Generate a mock response for testing V3 features."""
        
        # Memory-based responses
        if "what's my favorite plane" in message.lower():
            if "747" in memory_context:
                return "you love the 747 pookie! 😊 the queen of the skies girll! ✈️ such a classic choice! 🙌"
            elif "a380" in memory_context:
                return "you love the A380 pookie! 😊 the biggest passenger plane girll! ✈️ amazing choice! 🙌"
            elif "787" in memory_context:
                return "you love the 787 Dreamliner pookie! 😊 such a modern and efficient plane girll! ✈️ 🙌"
        
        if "what's my name" in message.lower():
            if "alex" in memory_context.lower():
                return "you're Alex pookie! 😊 girll! 🙌"
            elif "sarah" in memory_context.lower():
                return "you're Sarah pookie! 😊 girll! 🙌"
            elif "name:" in memory_context.lower():
                name = memory_context.split("Name: ")[1].split(" |")[0] if "Name: " in memory_context else "friend"
                return f"you're {name} pookie! 😊 girll! 🙌"
        
        if "where am i traveling" in message.lower() or "my trip" in message.lower():
            if "tokyo" in memory_context.lower():
                return "you're flying to Tokyo pookie! 😊 so exciting girll! ✈️ 🙌"
            elif "travel:" in memory_context.lower():
                destination = memory_context.split("Travel: ")[1].split(" |")[0] if "Travel: " in memory_context else "somewhere amazing"
                return f"you're going to {destination} pookie! 😊 have a great trip girll! ✈️ 🙌"
        
        # RAG-enhanced responses
        if rag_result:
            if "boeing 787" in message.lower():
                return "the 787 Dreamliner is amazing pookie! 😊 it uses composite materials and has better fuel efficiency girll! ✈️ plus those bigger windows and better cabin pressure! 🙌"
            elif "a380" in message.lower():
                return "the A380 is the world's largest passenger airliner pookie! 😊 it has two full decks and can carry over 500 passengers girll! ✈️ so impressive! 🙌"
            elif "747" in message.lower():
                return "the 747 is iconic pookie! 😊 the queen of the skies with that distinctive hump girll! ✈️ first wide-body jet and still beautiful! 🙌"
        
        # Greetings
        greetings = ["heya", "hello", "hi", "sup", "hey"]
        if any(greeting in message.lower() for greeting in greetings):
            return "heya pookie! 😊 how's it going girll! ✈️ 🙌"
        
        # Technical questions
        if "hydraulic" in message.lower():
            return "hydraulic systems use pressurized fluid to power flight controls, landing gear, and brakes pookie! 😊 they're super important for controlling the plane girll! ✈️ 🙌"
        
        if "engine fail" in message.lower():
            return "planes can fly safely on one engine pookie! 😊 pilots are trained extensively for this girll! ✈️ they'll head to the nearest suitable airport! 🙌"
        
        if "turbulence" in message.lower():
            return "turbulence is just bumpy air pookie! 😊 it's uncomfortable but planes are built to handle it girll! ✈️ totally safe! 🙌"
        
        # Aviation enthusiasm
        if "plane" in message.lower() or "aircraft" in message.lower() or "aviation" in message.lower():
            return "omg i love talking about aviation pookie! 😊 planes are so amazing girll! ✈️ what would you like to know? 🙌"
        
        # Default response
        return "that's interesting pookie! 😊 tell me more about aviation girll! ✈️ 🙌"
    
    def run_bot(self):
        """Run the bot."""
        try:
            self.run(self.bot_token)
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user")
        except Exception as e:
            print(f"\n  Bot error: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Main entry point."""
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Get configuration
    bot_token = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('DISCORD_TOKEN')
    
    if not bot_token:
        print("\n" + "─" * 60)
        print("  Aviation Girl V3 - Simple Version")
        print("─" * 60)
        print("\n    Error: Discord bot token not found!")
        print("\n  Please set DISCORD_BOT_TOKEN in your .env file")
        print("─" * 60 + "\n")
        return
    
    # Create and run bot
    print("\n  Starting Aviation Girl V3 (Simple Version)...")
    print("Features: Memory + RAG + Mock Responses")
    
    bot = AviationGirlV3Simple(bot_token)
    bot.run_bot()

if __name__ == "__main__":
    main()