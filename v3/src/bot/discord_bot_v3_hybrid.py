"""Aviation Girl V3 Discord Bot - Hybrid Version (Simple + Real Model)."""
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

class AviationGirlV3Hybrid(discord.Client):
    """Aviation Girl V3 - Hybrid version with gradual model loading."""
    
    def __init__(self, model_path: str, bot_token: str, use_gpu: bool = True):
        super().__init__(intents=INTENTS)
        self.bot_token = bot_token
        self.model_path = model_path
        self.use_gpu = use_gpu
        
        # Initialize systems
        self.memory = FastMemory("user_memory.json")
        self.rag = WikipediaRAG(max_context_length=500)
        
        # Model loading state
        self.model = None
        self.tokenizer = None
        self.model_loaded = False
        self.model_loading = False
        
        print("  Memory system initialized")
        print("  RAG system initialized")

    async def on_ready(self):
        """Called when bot is ready."""
        print("\n" + "─" * 60)
        print("  Aviation Girl V3 - Hybrid Version Ready!")
        print("─" * 60)
        print(f'  Logged in as: {self.user}')
        print(f'  Bot ID: {self.user.id}')
        print("    Memory system ready!")
        print("    Wikipedia RAG ready!")
        print("  🔄 Starting model loading...")
        print("─" * 60 + "\n")
        
        # Start model loading in background
        asyncio.create_task(self.load_model_gradually())
    
    async def load_model_gradually(self):
        """Load model gradually with detailed status updates."""
        if self.model_loading:
            return
        
        self.model_loading = True
        
        try:
            print("🔄 Step 1: Checking model path...")
            
            # Check if model path exists
            if self.model_path and not Path(self.model_path).exists():
                # Try relative to project root
                project_root = Path(__file__).parent.parent.parent.parent
                full_model_path = project_root / self.model_path
                if full_model_path.exists():
                    self.model_path = str(full_model_path)
                    print(f"  Found model at: {self.model_path}")
                else:
                    print(f"⚠️ Model not found: {self.model_path}")
                    print("   Will use base model without adapter")
                    self.model_path = None
            elif self.model_path:
                print(f"  Model path confirmed: {self.model_path}")
            
            print("🔄 Step 2: Testing model loading...")
            
            # Try to load just the tokenizer first
            try:
                from transformers import AutoTokenizer
                print("   Loading tokenizer...")
                tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct", trust_remote_code=True)
                print("     Tokenizer loaded successfully")
                
                # Now try the full model loading
                print("🔄 Step 3: Loading full model (this may take a while)...")
                await self._attempt_model_loading()
                
            except Exception as e:
                print(f"     Model loading failed: {e}")
                print("   Bot will continue with mock responses")
                
        except Exception as e:
            print(f"  Model loading error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self.model_loading = False
    
    async def _attempt_model_loading(self):
        """Attempt to load the model with detailed error handling."""
        try:
            # Import model loading functions
            from model.loader import load_base_with_adapter, get_device
            from model.generator import generate_response
            
            print("   Detecting hardware...")
            device = get_device()
            has_gpu = "cuda" in str(device) or "directml" in str(device)
            print(f"   Device detected: {device}")
            
            base_model = "Qwen/Qwen2.5-7B-Instruct"
            
            # Try loading in executor to not block Discord
            loop = asyncio.get_event_loop()
            
            if self.use_gpu and has_gpu:
                print(f"   Attempting GPU loading with 8-bit quantization...")
                try:
                    self.model, self.tokenizer = await loop.run_in_executor(
                        None,
                        lambda: load_base_with_adapter(
                            base_model, 
                            self.model_path,
                            use_8bit=True,
                            force_cpu=False
                        )
                    )
                    print("     GPU loading successful!")
                    self.model_loaded = True
                    return
                except Exception as e:
                    print(f"   ⚠️ GPU loading failed: {e}")
                    print("   Trying CPU mode...")
            
            # CPU fallback
            print("   Loading on CPU (slower but more reliable)...")
            self.model, self.tokenizer = await loop.run_in_executor(
                None,
                lambda: load_base_with_adapter(
                    base_model, 
                    self.model_path,
                    use_8bit=False,
                    force_cpu=True
                )
            )
            print("     CPU loading successful!")
            self.model_loaded = True
            
            print("\n🎉 Model loading complete!")
            print("  Aviation Girl V3 is now fully ready!")
            print("  All features active: 7B Model + Memory + RAG")
            
        except Exception as e:
            print(f"     Model loading failed: {e}")
            print("   Bot will continue with enhanced mock responses")
            import traceback
            traceback.print_exc()
    
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
        """Process message with V3 features (memory + RAG + model/mock)"""
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
            
            # Generate response
            if self.model_loaded and self.model and self.tokenizer:
                # Use real 7B model
                response = await self._generate_with_model(user_message, memory_context, rag_context)
            else:
                # Use enhanced mock responses
                response = self._generate_enhanced_mock_response(user_message, memory_context, rag_result)
                if self.model_loading:
                    response += "\n\n*🔄 7B model loading in background...*"
                elif not self.model_loaded:
                    response += "\n\n*⚠️ Using enhanced responses (7B model unavailable)*"
            
            # Add source citation if RAG was used
            if rag_result:
                response += f"\n\n*Source: [Wikipedia]({rag_result['url']})*"
            
            return response
            
        except Exception as e:
            print(f"Error processing message: {e}")
            return "sorry pookie! 😊 something went wrong girll! ✈️"
    
    async def _generate_with_model(self, user_message, memory_context, rag_context):
        """Generate response using the real 7B model."""
        try:
            from model.generator import generate_response
            
            # Build prompt with memory and RAG
            prompt_parts = []
            
            if memory_context:
                prompt_parts.append(f"Memory: {memory_context}")
            
            if rag_context:
                prompt_parts.append(f"Context: {rag_context}")
            
            prompt_parts.append(f"User: {user_message}")
            prompt_parts.append("Assistant:")
            
            prompt = "\n".join(prompt_parts)
            
            # Generate response using 7B model
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: generate_response(
                    self.model,
                    self.tokenizer,
                    prompt,
                    max_new_tokens=150,
                    temperature=0.8
                )
            )
            
            return response
            
        except Exception as e:
            print(f"Model generation error: {e}")
            # Fallback to mock response
            return self._generate_enhanced_mock_response(user_message, memory_context, None)
    
    def _generate_enhanced_mock_response(self, message: str, memory_context: str, rag_result: dict) -> str:
        """Generate enhanced mock response with V3 features."""
        
        # Memory-based responses
        if "what's my favorite plane" in message.lower():
            if "747" in memory_context:
                return "you love the 747 pookie! 😊 the queen of the skies girll! ✈️ such a classic choice with that iconic hump! 🙌"
            elif "a380" in memory_context:
                return "you love the A380 pookie! 😊 the biggest passenger plane girll! ✈️ two full decks of awesomeness! 🙌"
            elif "787" in memory_context:
                return "you love the 787 Dreamliner pookie! 😊 such a modern and efficient plane girll! ✈️ those composite materials! 🙌"
        
        if "what's my name" in message.lower():
            if "name:" in memory_context.lower():
                name = memory_context.split("Name: ")[1].split(" |")[0] if "Name: " in memory_context else "friend"
                return f"you're {name} pookie! 😊 girll! 🙌"
        
        if "where am i traveling" in message.lower() or "my trip" in message.lower():
            if "travel:" in memory_context.lower():
                destination = memory_context.split("Travel: ")[1].split(" |")[0] if "Travel: " in memory_context else "somewhere amazing"
                return f"you're going to {destination} pookie! 😊 have a great trip girll! ✈️ 🙌"
        
        # Technical aviation questions
        if "hydraulic" in message.lower():
            return "hydraulic systems use pressurized fluid around 3,000 psi to power flight controls, landing gear, and brakes pookie! 😊 most planes have multiple redundant systems for safety girll! ✈️ 🙌"
        
        if "engine fail" in message.lower():
            return "planes can fly safely on one engine pookie! 😊 twin-engine planes are certified for ETOPS - extended operations girll! ✈️ pilots train extensively for this scenario! 🙌"
        
        if "turbulence" in message.lower():
            return "turbulence is just bumpy air pookie! 😊 it's uncomfortable but planes are built to handle much more than they'll ever see girll! ✈️ totally safe! 🙌"
        
        if "787" in message.lower():
            return "the 787 Dreamliner is amazing pookie! 😊 it uses composite materials for better fuel efficiency and has bigger windows girll! ✈️ plus better cabin pressure! 🙌"
        
        if "a380" in message.lower():
            return "the A380 is incredible pookie! 😊 world's largest passenger airliner with two full decks girll! ✈️ can carry over 500 passengers! 🙌"
        
        if "747" in message.lower():
            return "the 747 is iconic pookie! 😊 the queen of the skies with that distinctive hump girll! ✈️ first wide-body jet and still beautiful! 🙌"
        
        # Greetings
        greetings = ["heya", "hello", "hi", "sup", "hey"]
        if any(greeting in message.lower() for greeting in greetings):
            return "heya pookie! 😊 how's it going girll! ✈️ ready to talk about some amazing planes? 🙌"
        
        # Aviation enthusiasm
        if "plane" in message.lower() or "aircraft" in message.lower() or "aviation" in message.lower():
            return "omg i love talking about aviation pookie! 😊 planes are so amazing girll! ✈️ what would you like to know? 🙌"
        
        # Default response
        return "that's interesting pookie! 😊 tell me more about aviation girll! ✈️ i love learning new things! 🙌"
    
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
    model_path = os.getenv('MODEL_PATH', 'models/qwan_7b/aviation_girl_v3_adapter')
    use_gpu = os.getenv('USE_GPU', 'true').lower() == 'true'
    
    if not bot_token:
        print("\n" + "─" * 60)
        print("  Aviation Girl V3 - Hybrid Version")
        print("─" * 60)
        print("\n    Error: Discord bot token not found!")
        print("\n  Please set DISCORD_BOT_TOKEN in your .env file")
        print("─" * 60 + "\n")
        return
    
    # Create and run bot
    print("\n  Starting Aviation Girl V3 (Hybrid Version)...")
    print("Features: Memory + RAG + Enhanced Responses + 7B Model Loading")
    
    bot = AviationGirlV3Hybrid(model_path, bot_token, use_gpu)
    bot.run_bot()

if __name__ == "__main__":
    main()