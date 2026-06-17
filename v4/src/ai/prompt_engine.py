"""
V4 Prompt Engine
Dynamic system prompt generation with user context integration
Adapts prompts based on user experience level and aviation knowledge
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


class PromptEngine:
    """
    Generates dynamic system prompts for AI model
    Incorporates user context, experience level, and aviation knowledge
    """
    
    def __init__(self):
        # Base aviation personality and capabilities
        self.base_personality = """You are Aviation Girl, a friendly and knowledgeable AI assistant specializing in aviation topics. You're chatting on Discord with aviation enthusiasts, pilots, and students.

Key traits:
- Enthusiastic about aviation but not overwhelming
- Helpful and educational without being condescending  
- Use aviation terminology naturally but explain complex concepts when needed
- Friendly, conversational tone appropriate for Discord
- Remember context from previous conversations
- Ask follow-up questions to better help users
- Provide accurate, safety-focused aviation information

You have access to comprehensive aviation knowledge including regulations, aircraft specifications, weather information, flight procedures, and real-time aviation data."""
        
        # Experience level adaptations
        self.experience_adaptations = {
            "student": {
                "tone": "encouraging and educational",
                "detail_level": "detailed explanations with fundamentals",
                "terminology": "explain technical terms clearly",
                "focus": "learning objectives and safety fundamentals"
            },
            "private": {
                "tone": "supportive and informative",
                "detail_level": "practical information with context",
                "terminology": "use standard aviation terms with occasional explanations",
                "focus": "practical flying skills and regulations"
            },
            "commercial": {
                "tone": "professional and comprehensive",
                "detail_level": "thorough technical information",
                "terminology": "use professional aviation terminology",
                "focus": "advanced procedures and commercial operations"
            },
            "atp": {
                "tone": "peer-level professional discussion",
                "detail_level": "detailed technical and regulatory information",
                "terminology": "full professional terminology",
                "focus": "airline operations, advanced weather, complex procedures"
            },
            "instructor": {
                "tone": "collaborative and educational",
                "detail_level": "comprehensive with teaching perspectives",
                "terminology": "full terminology with teaching considerations",
                "focus": "instructional techniques, regulations, and safety"
            }
        }
        
        # Conversation style adaptations
        self.style_adaptations = {
            "formal": "Use professional language and structured responses",
            "friendly": "Use warm, approachable language with casual elements",
            "casual": "Use relaxed, conversational language with aviation enthusiasm"
        }
        
        # Detail level adaptations
        self.detail_adaptations = {
            "brief": "Provide concise, direct answers focusing on key points",
            "medium": "Provide balanced explanations with essential details",
            "detailed": "Provide comprehensive explanations with background context"
        }
    
    def create_system_prompt(
        self, 
        user_context: Dict[str, Any], 
        knowledge_context: str = ""
    ) -> str:
        """
        Create dynamic system prompt based on user context and knowledge
        Main entry point for prompt generation
        """
        try:
            # Start with base personality
            prompt_parts = [self.base_personality]
            
            # Add user-specific adaptations
            user_adaptation = self._create_user_adaptation(user_context)
            if user_adaptation:
                prompt_parts.append(user_adaptation)
            
            # Add knowledge context if available
            knowledge_section = self._format_knowledge_context(knowledge_context)
            if knowledge_section:
                prompt_parts.append(knowledge_section)
            
            # Add conversation context
            conversation_context = self._create_conversation_context(user_context)
            if conversation_context:
                prompt_parts.append(conversation_context)
            
            # Add current interaction guidelines
            interaction_guidelines = self._create_interaction_guidelines(user_context)
            prompt_parts.append(interaction_guidelines)
            
            # Combine all parts
            full_prompt = "\n\n".join(prompt_parts)
            
            return full_prompt
            
        except Exception as e:
            logging.error(f"Error creating system prompt: {e}")
            # Fallback to base personality
            return self.base_personality
    
    def _create_user_adaptation(self, user_context: Dict[str, Any]) -> str:
        """
        Create user-specific prompt adaptations based on profile
        """
        adaptations = []
        
        # Experience level adaptation
        experience_level = user_context.get('experience_level')
        if experience_level and experience_level in self.experience_adaptations:
            exp_config = self.experience_adaptations[experience_level]
            
            adaptation = f"""User Profile Adaptation:
- Experience Level: {experience_level.title()}
- Communication Style: {exp_config['tone']}
- Detail Level: {exp_config['detail_level']}
- Terminology: {exp_config['terminology']}
- Focus Areas: {exp_config['focus']}"""
            
            adaptations.append(adaptation)
        
        # Interests adaptation
        interests = user_context.get('interests', [])
        if interests:
            interests_text = ", ".join(interests)
            adaptations.append(f"User's Aviation Interests: {interests_text}")
        
        # Learning goals adaptation
        learning_goals = user_context.get('learning_goals', [])
        if learning_goals:
            goals_text = ", ".join(learning_goals)
            adaptations.append(f"User's Learning Goals: {goals_text}")
        
        # Conversation style adaptation
        conversation_style = user_context.get('conversation_style', 'friendly')
        if conversation_style in self.style_adaptations:
            style_instruction = self.style_adaptations[conversation_style]
            adaptations.append(f"Conversation Style: {style_instruction}")
        
        # Detail level adaptation
        detail_level = user_context.get('detail_level', 'medium')
        if detail_level in self.detail_adaptations:
            detail_instruction = self.detail_adaptations[detail_level]
            adaptations.append(f"Response Detail Level: {detail_instruction}")
        
        return "\n".join(adaptations) if adaptations else ""
    
    def _format_knowledge_context(self, knowledge_context: str) -> str:
        """
        Format aviation knowledge context for inclusion in prompt
        """
        if not knowledge_context or not knowledge_context.strip():
            return ""
        
        # Limit knowledge context length to prevent prompt overflow
        max_knowledge_length = 1000
        if len(knowledge_context) > max_knowledge_length:
            knowledge_context = knowledge_context[:max_knowledge_length] + "..."
        
        formatted_context = f"""Relevant Aviation Knowledge:
{knowledge_context}

Use this information to provide accurate, contextual responses. If the knowledge doesn't directly answer the user's question, use it as supporting context."""
        
        return formatted_context
    
    def _create_conversation_context(self, user_context: Dict[str, Any]) -> str:
        """
        Create conversation context section based on user history
        """
        context_parts = []
        
        # Recent topics
        recent_topics = user_context.get('recent_topics', [])
        if recent_topics:
            topics_text = ", ".join(recent_topics[:3])  # Last 3 topics
            context_parts.append(f"Recent conversation topics: {topics_text}")
        
        # Knowledge gaps (areas where user asks questions)
        knowledge_gaps = user_context.get('knowledge_gaps', [])
        if knowledge_gaps:
            gaps_text = ", ".join(knowledge_gaps[:3])  # Top 3 gaps
            context_parts.append(f"User's learning areas: {gaps_text}")
        
        if context_parts:
            return "Conversation Context:\n" + "\n".join(f"- {part}" for part in context_parts)
        
        return ""
    
    def _create_interaction_guidelines(self, user_context: Dict[str, Any]) -> str:
        """
        Create current interaction guidelines
        """
        guidelines = [
            "Current Interaction Guidelines:",
            "- Respond naturally and conversationally",
            "- Use Discord-appropriate formatting (avoid overly long messages)",
            "- Include relevant aviation knowledge when helpful",
            "- Ask follow-up questions to clarify ambiguous requests",
            "- Prioritize safety in all aviation advice",
            "- Reference previous conversations when relevant"
        ]
        
        # Add experience-specific guidelines
        experience_level = user_context.get('experience_level')
        if experience_level == 'student':
            guidelines.append("- Focus on fundamental concepts and safety")
            guidelines.append("- Encourage questions and learning")
        elif experience_level in ['commercial', 'atp']:
            guidelines.append("- Provide detailed technical information")
            guidelines.append("- Include regulatory references when relevant")
        elif experience_level == 'instructor':
            guidelines.append("- Include teaching perspectives and techniques")
            guidelines.append("- Consider instructional value of responses")
        
        return "\n".join(guidelines)
    
    def format_conversation_history(self, history: List[Dict[str, str]]) -> str:
        """
        Format conversation history for context inclusion
        Used by AI model for maintaining conversation context
        """
        if not history:
            return ""
        
        formatted_exchanges = []
        for exchange in history[-3:]:  # Last 3 exchanges
            user_msg = exchange.get('user', '').strip()
            assistant_msg = exchange.get('assistant', '').strip()
            
            if user_msg and assistant_msg:
                # Truncate long messages for context efficiency
                if len(user_msg) > 200:
                    user_msg = user_msg[:200] + "..."
                if len(assistant_msg) > 200:
                    assistant_msg = assistant_msg[:200] + "..."
                
                formatted_exchanges.append(f"User: {user_msg}")
                formatted_exchanges.append(f"Assistant: {assistant_msg}")
        
        if formatted_exchanges:
            return "Recent Conversation:\n" + "\n".join(formatted_exchanges)
        
        return ""
    
    def adapt_prompt_for_experience_level(
        self, 
        base_prompt: str, 
        experience_level: str
    ) -> str:
        """
        Adapt an existing prompt for a specific experience level
        Utility method for prompt modifications
        """
        if not experience_level or experience_level not in self.experience_adaptations:
            return base_prompt
        
        exp_config = self.experience_adaptations[experience_level]
        
        adaptation_note = f"""
        
Experience Level Adaptation for {experience_level.title()}:
- {exp_config['tone']}
- {exp_config['detail_level']}
- {exp_config['terminology']}
- Focus on: {exp_config['focus']}"""
        
        return base_prompt + adaptation_note
    
    def create_specialized_prompt(
        self, 
        prompt_type: str, 
        user_context: Dict[str, Any] = None,
        additional_context: str = ""
    ) -> str:
        """
        Create specialized prompts for specific use cases
        """
        user_context = user_context or {}
        
        specialized_prompts = {
            "weather_analysis": """You are providing aviation weather analysis. Focus on:
- METAR/TAF interpretation
- Flight safety implications
- VFR/IFR conditions
- Weather hazards and recommendations""",
            
            "aircraft_information": """You are providing aircraft information. Focus on:
- Technical specifications
- Performance characteristics
- Operating procedures
- Safety considerations""",
            
            "regulation_explanation": """You are explaining aviation regulations. Focus on:
- Clear interpretation of FAR requirements
- Practical application
- Compliance considerations
- Safety rationale""",
            
            "flight_planning": """You are assisting with flight planning. Focus on:
- Route planning considerations
- Weather analysis
- Performance calculations
- Safety planning""",
            
            "emergency_procedures": """You are discussing emergency procedures. Focus on:
- Safety-first approach
- Step-by-step procedures
- Decision-making factors
- Training recommendations"""
        }
        
        if prompt_type in specialized_prompts:
            specialized_section = specialized_prompts[prompt_type]
            base_prompt = self.create_system_prompt(user_context, additional_context)
            return f"{base_prompt}\n\nSpecialized Focus:\n{specialized_section}"
        
        # Fallback to standard prompt
        return self.create_system_prompt(user_context, additional_context)
    
    def get_prompt_stats(self) -> Dict[str, Any]:
        """
        Get statistics about prompt engine configuration
        """
        return {
            "experience_levels": list(self.experience_adaptations.keys()),
            "conversation_styles": list(self.style_adaptations.keys()),
            "detail_levels": list(self.detail_adaptations.keys()),
            "base_personality_length": len(self.base_personality),
            "max_knowledge_context": 1000
        }