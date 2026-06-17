"""
V4 AI Model Manager
Handles loading and interfacing with the base AI model
No fine-tuning - just smart prompting and context management
"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, GenerationConfig
import logging
from typing import Optional, Dict, Any, List
import asyncio
import json
import os

class AIModelManager:
    """
    Manages the base AI model for natural conversation
    Focuses on prompt engineering rather than fine-tuning
    """
    
    def __init__(self, model_name: str = "Qwen/Qwen2.5-7B-Instruct"):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self.device = None
        self.is_loaded = False
        
        # Generation settings
        self.generation_config = GenerationConfig(
            max_new_tokens=512,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            pad_token_id=None,  # Will be set after tokenizer loads
            eos_token_id=None,  # Will be set after tokenizer loads
        )
        
    async def load_model(self):
        """Load the AI model and tokenizer"""
        logging.info(f"Loading AI model: {self.model_name}")
        
        try:
            # Determine device
            if torch.cuda.is_available():
                self.device = "cuda"
                logging.info("Using GPU acceleration")
            else:
                self.device = "cpu"
                logging.info("Using CPU (GPU not available)")
            
            # Load tokenizer
            logging.info("Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )
            
            # Set pad token if not exists
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model
            logging.info("Loading model...")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None,
                trust_remote_code=True
            )
            
            if self.device == "cpu":
                self.model = self.model.to(self.device)
            
            # Update generation config with tokenizer info
            self.generation_config.pad_token_id = self.tokenizer.pad_token_id
            self.generation_config.eos_token_id = self.tokenizer.eos_token_id
            
            self.is_loaded = True
            logging.info("AI model loaded successfully")
            
        except Exception as e:
            logging.error(f"Failed to load AI model: {e}")
            raise
    
    def create_system_prompt(self, user_context: Dict[str, Any], knowledge_context: str = "") -> str:
        """
        Create dynamic system prompt based on user context and knowledge
        This is where the magic happens - no fine-tuning needed
        """
        
        # Base aviation personality
        base_prompt = """You are Aviation Girl, a friendly and knowledgeable AI assistant specializing in aviation topics. You're chatting on Discord with aviation enthusiasts, pilots, and students.

Key traits:
- Enthusiastic about aviation but not overwhelming
- Helpful and educational without being condescending  
- Use aviation terminology naturally but explain complex concepts
- Friendly, conversational tone appropriate for Discord
- Remember context from previous conversations
- Ask follow-up questions to better help users

You have access to comprehensive aviation knowledge including regulations, aircraft specifications, weather information, and flight procedures."""
        
        # Add user-specific context
        user_info = ""
        if user_context:
            experience = user_context.get('experience_level')
            interests = user_context.get('interests', [])
            goals = user_context.get('learning_goals', [])
            
            if experience:
                user_info += f"\nUser's aviation experience: {experience}"
            if interests:
                user_info += f"\nUser's interests: {', '.join(interests)}"
            if goals:
                user_info += f"\nUser's learning goals: {', '.join(goals)}"
        
        # Add knowledge context if available
        knowledge_info = ""
        if knowledge_context:
            knowledge_info = f"\n\nRelevant aviation information:\n{knowledge_context}"
        
        # Combine all parts
        full_prompt = base_prompt + user_info + knowledge_info
        
        return full_prompt
    
    async def generate_response(
        self, 
        message: str, 
        user_context: Dict[str, Any] = None,
        knowledge_context: str = "",
        conversation_history: List[Dict[str, str]] = None
    ) -> str:
        """
        Generate AI response with full context
        """
        if not self.is_loaded:
            return "Sorry, I'm still starting up. Please try again in a moment."
        
        try:
            # Create system prompt
            system_prompt = self.create_system_prompt(user_context, knowledge_context)
            
            # Build conversation
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history (last 5 exchanges to stay within context)
            if conversation_history:
                for exchange in conversation_history[-5:]:
                    messages.append({"role": "user", "content": exchange.get("user", "")})
                    messages.append({"role": "assistant", "content": exchange.get("assistant", "")})
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Apply chat template
            formatted_prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            # Tokenize
            inputs = self.tokenizer(
                formatted_prompt,
                return_tensors="pt",
                truncation=True,
                max_length=4000  # Leave room for response
            ).to(self.device)
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    generation_config=self.generation_config,
                    use_cache=True
                )
            
            # Decode response
            response = self.tokenizer.decode(
                outputs[0][inputs['input_ids'].shape[1]:],
                skip_special_tokens=True
            ).strip()
            
            # Clean up response
            response = self._clean_response(response)
            
            return response
            
        except Exception as e:
            logging.error(f"Error generating response: {e}")
            return "Sorry, I encountered an error processing your message. Please try again."
    
    def _clean_response(self, response: str) -> str:
        """Clean up AI response for Discord"""
        # Remove any system artifacts
        response = response.strip()
        
        # Remove common AI artifacts
        artifacts = [
            "Human:", "Assistant:", "User:", "AI:",
            "<|im_start|>", "<|im_end|>", "<|endoftext|>"
        ]
        
        for artifact in artifacts:
            response = response.replace(artifact, "").strip()
        
        # Ensure reasonable length for Discord
        if len(response) > 1900:  # Leave room for embeds
            response = response[:1900] + "..."
        
        return response
    
    async def evaluate_memory_relevance(self, conversation_text: str) -> Dict[str, Any]:
        """
        Use AI to determine what's worth remembering from a conversation
        Returns relevance score and extracted information
        """
        if not self.is_loaded:
            return {"relevance_score": 0, "extracted_info": {}}
        
        try:
            prompt = f"""Analyze this aviation conversation and determine what information should be remembered about the user:

Conversation: {conversation_text}

Extract and score (1-10) the relevance of:
1. Aviation experience level mentioned
2. Aircraft interests or preferences  
3. Learning goals or objectives
4. Specific questions or knowledge gaps
5. Personal aviation experiences shared

Respond in JSON format:
{{
    "relevance_score": <1-10>,
    "experience_level": "<level if mentioned>",
    "interests": ["<interests>"],
    "learning_goals": ["<goals>"],
    "knowledge_gaps": ["<gaps>"],
    "experiences": ["<experiences>"]
}}"""

            # Simple generation for analysis
            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2000).to(self.device)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=200,
                    temperature=0.3,  # Lower temperature for more consistent JSON
                    do_sample=True
                )
            
            response = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True).strip()
            
            # Try to parse JSON response
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return {"relevance_score": 5, "extracted_info": {"raw_analysis": response}}
                
        except Exception as e:
            logging.error(f"Error evaluating memory relevance: {e}")
            return {"relevance_score": 0, "extracted_info": {}}
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "is_loaded": self.is_loaded,
            "parameters": sum(p.numel() for p in self.model.parameters()) if self.model else 0
        }