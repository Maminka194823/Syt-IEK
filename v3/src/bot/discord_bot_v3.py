"""Aviation Girl V3 Discord Bot with Memory and RAG."""
import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import sys
import os
import asyncio
from pathlib import Path

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent))

from memory.fast_memory import FastMemory
from rag.wikipedia_rag import WikipediaRAG
from model.loader import load_base_with_adapter, get_device
from model.generator import generate_response

# Bot configuration
INTENTS = discord.Intents.default()
INTENTS.message_content = True

class RewriteModal(Modal, title="Rewrite Response"):
    """Modal for rewriting the AI response with additional prompt"""
    
    additional_prompt = TextInput(
        label="Additional Instructions",
        placeholder="e.g., 'make it more casual' or 'add emojis'",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )
    
    def __init__(self, bot, original_message, original_response, message_to_reply):
        super().__init__()
        self.bot = bot
        self.original_message = original_message
        self.original_response = original_response
        self.message_to_reply = message_to_reply
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Generate new response with additional instructions
        new_response = await self.bot.generate_response_with_instructions(
            self.original_message, 
            self.additional_prompt.value
        )
        
        # Show new response with buttons
        view = ResponseView(self.bot, self.original_message, new_response, self.message_to_reply)
        await interaction.followup.send(
            f"**Rewritten Response:**\n{new_response}",
            view=view,
            ephemeral=True
        )

class ResponseView(View):
    """View with Cancel, Rewrite, and Send buttons"""
    
    def __init__(self, bot, original_message, ai_response, message_to_reply=None):
        super().__init__(timeout=300)  # Remove .0
        self.bot = bot
        self.original_message = original_message
        self.ai_response = ai_response
        self.message_to_reply = message_to_reply
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji=" ")
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content="  Cancelled. Response not sent.",
            view=None
        )
        self.stop()
    
    @discord.ui.button(label="Rewrite", style=discord.ButtonStyle.primary, emoji="✏️")
    async def rewrite_button(self, interaction: discord.Interaction, button: Button):
        modal = RewriteModal(self.bot, self.original_message, self.ai_response, self.message_to_reply)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Send", style=discord.ButtonStyle.success, emoji=" ")
    async def send_button(self, interaction: discord.Interaction, button: Button):
        if self.message_to_reply:
            try:
                await self.message_to_reply.reply(self.ai_response)
                await interaction.response.edit_message(
                    content="  Response sent!",
                    view=None
                )
            except Exception as e:
                await interaction.response.edit_message(
                    content=f"  Error sending message: {e}",
                    view=None
                )
        else:
            await interaction.response.edit_message(
                content="  Original message not found.",
                view=None
            )
        self.stop()

class AviationGirlV3(discord.Client):
    """Aviation Girl V3 with memory and RAG."""
    
    def __init__(self, model_path: str, bot_token: str, use_gpu: bool = True):
        super().__init__(intents=INTENTS)
        self.tree = app_commands.CommandTree(self)
        
        self.bot_token = bot_token
        self.model_path = model_path
        self.use_gpu = use_gpu
        
        # Initialize systems
        self.memory = FastMemory("user_memory.json")
        self.rag = WikipediaRAG(max_context_length=500)
        
        # Model will be loaded on ready
        self.model = None
        self.tokenizer = None
        self.model_loaded = False

    async def setup_hook(self):
        """Setup the bot"""
        await self.tree.sync()
        print("Bot commands synced!", flush=True)

    async def on_ready(self):
        """Called when bot is ready."""
        print("\n" + "─" * 60)
        print("  Aviation Girl V3 - Ready!")
        print("─" * 60)
        print(f'  Logged in as: {self.user}')
        print(f'  Bot ID: {self.user.id}')
        print("    Memory system ready!")
        print("    Wikipedia RAG ready!")
        print("  🔄 Loading 7B model in background...")
        print("─" * 60 + "\n")
        
        # Load model in background after bot is ready
        asyncio.create_task(self.load_model_background())
    
    async def load_model_background(self):
        """Load model in background without blocking Discord."""
        try:
            print("🔄 Starting model loading in background...")
            
            # Use asyncio to run in executor so it doesn't block
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._load_model_sync)
            
            self.model_loaded = True
            print("\n🎉 Model loading complete!")
            print("  Aviation Girl V3 is now fully ready!")
            print("  All features active: 7B Model + Memory + RAG")
            
        except Exception as e:
            print(f"\n  Model loading failed: {e}")
            print("⚠️ Bot will continue with mock responses")
            import traceback
            traceback.print_exc()
    
    async def load_model(self):
        """Load the Qwen2.5-7B model with adapter"""
        try:
            print("  [1/3] Detecting hardware...", flush=True)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._load_model_sync)
            self.model_loaded = True
            print("  [3/3]   Model loaded successfully!", flush=True)
        except Exception as e:
            print(f"    Error loading model: {e}", flush=True)
            print(f"  Bot will continue but AI features won't work.", flush=True)
            import traceback
            traceback.print_exc()
    
    def _load_model_sync(self):
        """Synchronous model loading"""
        print("🔄 Loading Qwen2.5-7B with adapter...")
        
        # Detect available hardware
        device = get_device()
        has_gpu = "cuda" in str(device) or "directml" in str(device)
        
        base_model = "Qwen/Qwen2.5-7B-Instruct"
        
        if self.use_gpu and has_gpu:
            print(f"   Using {device} with 8-bit quantization")
            try:
                self.model, self.tokenizer = load_base_with_adapter(
                    base_model, 
                    self.model_path,
                    use_8bit=True,
                    force_cpu=False
                )
                print("     GPU loading successful!")
                return
            except Exception as e:
                print(f"   ⚠️ GPU loading failed: {e}")
                print("   Falling back to CPU mode...")
        
        # CPU fallback
        print("   Using CPU mode (slower but reliable)")
        self.model, self.tokenizer = load_base_with_adapter(
            base_model, 
            self.model_path,
            use_8bit=False,
            force_cpu=True
        )
        print("     CPU loading successful!")
    
    async def on_message(self, message):
        """Handle incoming messages."""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if bot was mentioned or replied to
        bot_mentioned = self.user in message.mentions
        bot_replied_to = message.reference and message.reference.resolved and message.reference.resolved.author == self.user
        
        if bot_mentioned or bot_replied_to:
            if not self.model_loaded:
                await message.reply("⚠️ Model is still loading, please wait...")
                return
            
            # Show typing indicator
            async with message.channel.typing():
                # Process message with V3 features
                response = await self.process_message_v3(message)
                await message.reply(response)
    
    async def process_message_v3(self, message):
        """Process message with V3 features (memory + RAG + 7B model)"""
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
                # Use mock responses while model loads
                response = self._generate_mock_response(user_message, memory_context, rag_result)
                if not self.model_loaded:
                    response += "\n\n*⚠️ Model still loading - using temporary responses*"
            
            # Add source citation if RAG was used
            if rag_result:
                response += f"\n\n*Source: [Wikipedia]({rag_result['url']})*"
            
            return response
            
        except Exception as e:
            print(f"Error processing message: {e}")
            return "sorry pookie! 😊 something went wrong girll! ✈️"
    
    async def _generate_with_model(self, user_message, memory_context, rag_context):
        """Generate response using the 7B model."""
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
            self._generate_response_sync,
            prompt
        )
        
        return response
    
    def _generate_mock_response(self, message: str, memory_context: str, rag_result: dict) -> str:
        """Generate a mock response while model is loading."""
        
        # Memory-based responses
        if "what's my favorite plane" in message.lower():
            if "747" in memory_context:
                return "you love the 747 pookie! 😊 the queen of the skies girll! ✈️ such a classic choice! 🙌"
            elif "a380" in memory_context:
                return "you love the A380 pookie! 😊 the biggest passenger plane girll! ✈️ amazing choice! 🙌"
        
        if "what's my name" in message.lower():
            if "name:" in memory_context.lower():
                name = memory_context.split("Name: ")[1].split(" |")[0] if "Name: " in memory_context else "friend"
                return f"you're {name} pookie! 😊 girll! 🙌"
        
        # Greetings
        greetings = ["heya", "hello", "hi", "sup", "hey"]
        if any(greeting in message.lower() for greeting in greetings):
            return "heya pookie! 😊 how's it going girll! ✈️ 🙌"
        
        # Aviation topics
        if "plane" in message.lower() or "aircraft" in message.lower() or "aviation" in message.lower():
            return "omg i love talking about aviation pookie! 😊 planes are so amazing girll! ✈️ what would you like to know? 🙌"
        
        # Default
        return "that's interesting pookie! 😊 tell me more about aviation girll! ✈️ 🙌"
    
    def _generate_response_sync(self, prompt):
        """Generate response using the 7B model"""
        return generate_response(
            self.model,
            self.tokenizer,
            prompt,
            max_new_tokens=150,
            temperature=0.8
        )
    
    async def generate_response_with_instructions(self, message, instructions):
        """Generate response with additional instructions"""
        if not self.model_loaded:
            return "⚠️ Model is still loading, please wait..."
        
        try:
            # Build prompt with instructions
            prompt = f"Instructions: {instructions}\nUser: {message}\nAssistant:"
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self._generate_response_sync,
                prompt
            )
            return response
        except Exception as e:
            return f"  Error generating response: {e}"
    
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

# Create bot instance
bot = None

# Context menu command: Form Response
@app_commands.context_menu(name="Form Response")
async def form_response(interaction: discord.Interaction, message: discord.Message):
    """Right-click context menu to form AI response"""
    
    # Defer response (ephemeral = only you can see)
    await interaction.response.defer(ephemeral=True)
    
    # Check if model is loaded
    if not bot.model_loaded:
        await interaction.followup.send(
            "⚠️ AI model is still loading, please wait a moment...",
            ephemeral=True
        )
        return
    
    # Process message with V3 features
    ai_response = await bot.process_message_v3(message)
    
    # Create view with buttons
    view = ResponseView(bot, message.content, ai_response, message)
    
    # Send response with buttons (only visible to you)
    await interaction.followup.send(
        f"**Aviation Girl V3 Response:**\n{ai_response}\n\n*Choose an action:*",
        view=view,
        ephemeral=True
    )

def main():
    """Main entry point."""
    global bot
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Get configuration
    bot_token = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('DISCORD_TOKEN')
    model_path = os.getenv('MODEL_PATH', 'models/qwan_7b/aviation_girl_v3_adapter')
    use_gpu = os.getenv('USE_GPU', 'true').lower() == 'true'
    
    if not bot_token:
        print("\n" + "─" * 60)
        print("  Aviation Girl V3 - Discord Bot")
        print("─" * 60)
        print("\n    Error: Discord bot token not found!")
        print("\n  Please set one of these environment variables:")
        print("    • DISCORD_BOT_TOKEN=your_token_here")
        print("    • DISCORD_TOKEN=your_token_here")
        print("\n  Or create a .env file with:")
        print("    DISCORD_BOT_TOKEN=your_token_here")
        print("\n  Get your token from:")
        print("    https://discord.com/developers/applications")
        print("─" * 60 + "\n")
        return
    
    # Check if model exists (adjust path relative to project root)
    if model_path and not Path(model_path).exists():
        # Try relative to project root
        project_root = Path(__file__).parent.parent.parent
        full_model_path = project_root / model_path
        if full_model_path.exists():
            model_path = str(full_model_path)
        else:
            print(f"\n⚠️ Warning: Model path {model_path} not found")
            print("Using base model without fine-tuned adapter")
            model_path = None
    elif model_path:
        print(f"  Found trained model: {model_path}")
    
    # Create and run bot
    print("\n  Starting Aviation Girl V3...")
    print("Features: 7B Model + Memory + RAG + Discord Integration")
    
    bot = AviationGirlV3(model_path, bot_token, use_gpu)
    
    # Add context menu command to bot's tree
    bot.tree.add_command(form_response)
    
    bot.run_bot()

if __name__ == "__main__":
    main()