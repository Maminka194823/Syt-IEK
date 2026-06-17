"""
V4 User Profile Management
AI-driven memory system that learns about users over time
Enhanced with AI evaluation, automatic pruning, and feedback handling
"""

import json
import os
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import logging
import hashlib

class UserProfileManager:
    """
    Manages user profiles with AI-driven memory decisions
    Stores aviation-specific context and conversation history
    Enhanced with automatic pruning, context optimization, and feedback handling
    """
    
    def __init__(self, data_dir: str = "data/user_profiles", ai_orchestrator=None):
        self.data_dir = data_dir
        self.profiles_cache = {}
        self.conversation_cache = {}
        self.ai_orchestrator = ai_orchestrator  # For AI-driven memory evaluation
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Enhanced memory settings
        self.max_conversation_history = 50  # Per user
        self.memory_retention_days = 90
        self.relevance_threshold = 6  # AI scores 1-10, keep 6+
        self.context_optimization_threshold = 20  # Optimize after 20 conversations
        self.auto_prune_interval = 24 * 60 * 60  # 24 hours in seconds
        self.feedback_weight = 1.5  # Boost relevance for corrected information
        
        # Conversation pruning settings
        self.low_relevance_threshold = 4  # Remove conversations below this score
        self.context_window_size = 10  # Number of recent conversations to keep for context
        self.important_memory_limit = 30  # Maximum important conversations to keep
        
        # Track last pruning time
        self.last_pruning = {}  # user_id -> timestamp
        
    async def initialize(self):
        """
        Initialize user profile manager (async placeholder for compatibility)
        The actual initialization is done in __init__
        """
        # Nothing to do here - initialization is synchronous and done in __init__
        pass
        
    async def get_profile(self, user_id: int) -> Dict[str, Any]:
        """Get user profile, creating if doesn't exist"""
        user_id_str = str(user_id)
        
        # Check cache first
        if user_id_str in self.profiles_cache:
            return self.profiles_cache[user_id_str]
        
        # Load from file
        profile_path = os.path.join(self.data_dir, f"{user_id_str}.json")
        
        if os.path.exists(profile_path):
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    profile = json.load(f)
                self.profiles_cache[user_id_str] = profile
                return profile
            except Exception as e:
                logging.error(f"Error loading profile for {user_id}: {e}")
        
        # Create new profile
        profile = self._create_new_profile(user_id)
        self.profiles_cache[user_id_str] = profile
        await self._save_profile(user_id, profile)
        
        return profile
    
    def _create_new_profile(self, user_id: int) -> Dict[str, Any]:
        """Create a new user profile with default values"""
        return {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_active": datetime.utcnow().isoformat(),
            "conversation_count": 0,
            
            # Aviation-specific information
            "experience_level": None,  # student, private, commercial, atp, etc.
            "interests": [],  # aircraft types, flying activities, etc.
            "learning_goals": [],  # licenses, ratings, skills
            "knowledge_gaps": [],  # areas where user asks questions
            "aviation_experiences": [],  # personal flying stories, achievements
            
            # Conversation preferences
            "preferred_detail_level": "medium",  # brief, medium, detailed
            "conversation_style": "friendly",  # formal, friendly, casual
            "timezone": None,
            
            # Memory and context
            "important_conversations": [],  # High-relevance conversation summaries
            "recent_topics": [],  # Recent discussion topics
            "correction_history": [],  # When user corrects the AI
            "feedback_patterns": {},  # Patterns in user feedback and corrections
            
            # Enhanced memory management
            "context_optimization_score": 0.0,  # How well optimized the context is
            "last_context_optimization": None,
            "conversation_relevance_scores": [],  # Track relevance over time
            "pruning_history": [],  # Track when and what was pruned
            
            # Statistics
            "total_messages": 0,
            "aviation_questions_asked": 0,
            "helpful_responses_received": 0,
            "corrections_provided": 0,
            "context_optimizations": 0
        }
    
    async def update_profile_from_conversation(
        self, 
        user_id: int, 
        conversation_text: str,
        ai_analysis: Dict[str, Any] = None
    ):
        """
        Update user profile based on AI analysis of conversation
        Enhanced with automatic pruning and context optimization
        """
        profile = await self.get_profile(user_id)
        
        # Update basic stats
        profile["last_active"] = datetime.utcnow().isoformat()
        profile["total_messages"] += 1
        profile["conversation_count"] += 1
        
        # Get AI analysis if not provided
        if ai_analysis is None and self.ai_orchestrator:
            ai_analysis = await self.ai_orchestrator.evaluate_memory_relevance(conversation_text)
        elif ai_analysis is None:
            ai_analysis = {"relevance_score": 5, "extracted_info": {}}
        
        relevance_score = ai_analysis.get("relevance_score", 0)
        
        # Track relevance scores for trend analysis
        profile["conversation_relevance_scores"].append({
            "score": relevance_score,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep only recent relevance scores
        profile["conversation_relevance_scores"] = profile["conversation_relevance_scores"][-50:]
        
        if relevance_score >= self.relevance_threshold:
            # High relevance - update profile information
            extracted_info = ai_analysis.get("extracted_info", {})
            
            # Update experience level if mentioned
            if "experience_level" in extracted_info and extracted_info["experience_level"]:
                old_level = profile.get("experience_level")
                new_level = extracted_info["experience_level"]
                if old_level != new_level:
                    profile["experience_level"] = new_level
                    # Record this as an important update
                    self._record_profile_update(profile, "experience_level", old_level, new_level)
            
            # Add new interests (avoid duplicates, prioritize by relevance)
            new_interests = extracted_info.get("interests", [])
            for interest in new_interests:
                if interest and interest not in profile["interests"]:
                    profile["interests"].append(interest)
            
            # Add learning goals
            new_goals = extracted_info.get("learning_goals", [])
            for goal in new_goals:
                if goal and goal not in profile["learning_goals"]:
                    profile["learning_goals"].append(goal)
            
            # Track knowledge gaps with frequency
            new_gaps = extracted_info.get("knowledge_gaps", [])
            for gap in new_gaps:
                if gap and gap not in profile["knowledge_gaps"]:
                    profile["knowledge_gaps"].append(gap)
            
            # Store important conversation summary with enhanced metadata
            conversation_summary = {
                "timestamp": datetime.utcnow().isoformat(),
                "relevance_score": relevance_score,
                "summary": self._create_conversation_summary(conversation_text),
                "extracted_info": extracted_info,
                "conversation_hash": self._hash_conversation(conversation_text),
                "topics": self._extract_detailed_topics(conversation_text),
                "user_sentiment": ai_analysis.get("user_sentiment", "neutral")
            }
            
            profile["important_conversations"].append(conversation_summary)
            
            # Intelligent pruning of important conversations
            profile["important_conversations"] = await self._prune_important_conversations(
                profile["important_conversations"], user_id
            )
        
        # Update recent topics (always track)
        topic = self._extract_topic_from_conversation(conversation_text)
        if topic:
            profile["recent_topics"].insert(0, {
                "topic": topic,
                "timestamp": datetime.utcnow().isoformat(),
                "relevance_score": relevance_score
            })
            # Keep only last 10 topics
            profile["recent_topics"] = profile["recent_topics"][:10]
        
        # Check if context optimization is needed
        if profile["conversation_count"] % self.context_optimization_threshold == 0:
            await self._optimize_user_context(user_id, profile)
        
        # Check if automatic pruning is needed
        await self._check_and_perform_auto_pruning(user_id, profile)
        
        # Save updated profile
        await self._save_profile(user_id, profile)
    
    def _extract_topic_from_conversation(self, conversation_text: str) -> Optional[str]:
        """Extract main topic from conversation (enhanced keyword-based analysis)"""
        # Aviation keywords to identify topics
        aviation_topics = {
            "weather": ["weather", "metar", "taf", "wind", "visibility", "ceiling", "clouds", "turbulence"],
            "navigation": ["navigation", "gps", "vor", "ils", "approach", "departure", "waypoint", "fix"],
            "aircraft": ["cessna", "piper", "boeing", "airbus", "helicopter", "aircraft", "plane", "jet"],
            "regulations": ["far", "regulation", "rule", "legal", "requirement", "faa", "compliance"],
            "training": ["training", "lesson", "instructor", "student", "practice", "checkride", "exam"],
            "flight_planning": ["flight plan", "route", "fuel", "weight", "balance", "performance", "chart"],
            "emergency": ["emergency", "malfunction", "failure", "abort", "divert", "mayday", "pan pan"],
            "airports": ["airport", "runway", "taxiway", "tower", "ground", "atc", "clearance"],
            "licenses": ["license", "rating", "certificate", "private", "commercial", "atp", "instrument"]
        }
        
        conversation_lower = conversation_text.lower()
        topic_scores = {}
        
        # Score topics based on keyword frequency and context
        for topic, keywords in aviation_topics.items():
            score = 0
            for keyword in keywords:
                count = conversation_lower.count(keyword)
                score += count * (2 if len(keyword) > 5 else 1)  # Longer keywords get more weight
            topic_scores[topic] = score
        
        # Return the highest scoring topic if above threshold
        if topic_scores:
            best_topic = max(topic_scores, key=topic_scores.get)
            if topic_scores[best_topic] > 0:
                return best_topic
        
        return "general_aviation"
    
    def _create_conversation_summary(self, conversation_text: str, max_length: int = 300) -> str:
        """Create an intelligent summary of the conversation"""
        if len(conversation_text) <= max_length:
            return conversation_text
        
        # Try to find natural break points
        sentences = conversation_text.split('. ')
        summary = ""
        
        for sentence in sentences:
            if len(summary + sentence + '. ') <= max_length:
                summary += sentence + '. '
            else:
                break
        
        if not summary:
            # Fallback to simple truncation
            summary = conversation_text[:max_length-3] + "..."
        
        return summary.strip()
    
    def _hash_conversation(self, conversation_text: str) -> str:
        """Create a hash of the conversation for deduplication"""
        return hashlib.md5(conversation_text.encode()).hexdigest()[:16]
    
    def _extract_detailed_topics(self, conversation_text: str) -> List[str]:
        """Extract multiple topics from conversation with confidence scores"""
        topics = []
        conversation_lower = conversation_text.lower()
        
        # More detailed topic extraction
        detailed_topics = {
            "weather_interpretation": ["decode", "interpret", "metar", "taf", "weather"],
            "flight_training": ["solo", "dual", "instructor", "lesson", "maneuver"],
            "aircraft_systems": ["engine", "electrical", "hydraulic", "avionics", "system"],
            "navigation_procedures": ["approach", "departure", "hold", "intercept", "radial"],
            "emergency_procedures": ["engine failure", "electrical failure", "lost comm", "emergency"],
            "regulations_compliance": ["far", "regulation", "legal", "violation", "compliance"]
        }
        
        for topic, keywords in detailed_topics.items():
            if any(keyword in conversation_lower for keyword in keywords):
                topics.append(topic)
        
        return topics[:3]  # Return top 3 topics
    
    def _record_profile_update(self, profile: Dict[str, Any], field: str, old_value: Any, new_value: Any):
        """Record significant profile updates for tracking"""
        if "profile_updates" not in profile:
            profile["profile_updates"] = []
        
        update_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "field": field,
            "old_value": old_value,
            "new_value": new_value
        }
        
        profile["profile_updates"].append(update_record)
        # Keep only recent updates
        profile["profile_updates"] = profile["profile_updates"][-20:]
    
    async def _prune_important_conversations(
        self, 
        conversations: List[Dict[str, Any]], 
        user_id: int
    ) -> List[Dict[str, Any]]:
        """Intelligently prune important conversations based on relevance and age"""
        if len(conversations) <= self.important_memory_limit:
            return conversations
        
        # Sort by relevance score and recency
        def conversation_priority(conv):
            relevance = conv.get("relevance_score", 0)
            timestamp = datetime.fromisoformat(conv["timestamp"])
            age_days = (datetime.utcnow() - timestamp).days
            
            # Boost recent conversations and high relevance
            recency_boost = max(0, 30 - age_days) / 30  # 0-1 boost for conversations < 30 days
            return relevance + recency_boost
        
        # Sort by priority (highest first)
        sorted_conversations = sorted(conversations, key=conversation_priority, reverse=True)
        
        # Keep the top conversations
        pruned_conversations = sorted_conversations[:self.important_memory_limit]
        
        # Log pruning activity
        pruned_count = len(conversations) - len(pruned_conversations)
        if pruned_count > 0:
            logging.info(f"Pruned {pruned_count} conversations for user {user_id}")
        
        return pruned_conversations
    
    async def _optimize_user_context(self, user_id: int, profile: Dict[str, Any]):
        """Optimize user context for better AI responses"""
        try:
            # Calculate context optimization score
            relevance_scores = [score["score"] for score in profile.get("conversation_relevance_scores", [])]
            if relevance_scores:
                avg_relevance = sum(relevance_scores) / len(relevance_scores)
                profile["context_optimization_score"] = avg_relevance
            
            # Consolidate similar interests and goals
            profile["interests"] = self._consolidate_list_items(profile.get("interests", []))
            profile["learning_goals"] = self._consolidate_list_items(profile.get("learning_goals", []))
            profile["knowledge_gaps"] = self._consolidate_list_items(profile.get("knowledge_gaps", []))
            
            # Update optimization timestamp
            profile["last_context_optimization"] = datetime.utcnow().isoformat()
            profile["context_optimizations"] = profile.get("context_optimizations", 0) + 1
            
            logging.info(f"Optimized context for user {user_id}")
            
        except Exception as e:
            logging.error(f"Error optimizing context for user {user_id}: {e}")
    
    def _consolidate_list_items(self, items: List[str]) -> List[str]:
        """Consolidate similar items in a list to reduce redundancy"""
        if not items:
            return items
        
        # Simple consolidation - remove duplicates and very similar items
        consolidated = []
        for item in items:
            item_lower = item.lower()
            # Check if this item is too similar to existing ones
            is_duplicate = False
            for existing in consolidated:
                existing_lower = existing.lower()
                # Simple similarity check
                if (item_lower in existing_lower or existing_lower in item_lower or 
                    len(set(item_lower.split()) & set(existing_lower.split())) > len(item_lower.split()) * 0.7):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                consolidated.append(item)
        
        return consolidated[:10]  # Limit to top 10 items
    
    async def _check_and_perform_auto_pruning(self, user_id: int, profile: Dict[str, Any]):
        """Check if automatic pruning is needed and perform it"""
        current_time = datetime.utcnow()
        last_pruning = self.last_pruning.get(user_id)
        
        if last_pruning is None:
            self.last_pruning[user_id] = current_time
            return
        
        time_since_pruning = (current_time - last_pruning).total_seconds()
        
        if time_since_pruning >= self.auto_prune_interval:
            await self._perform_conversation_pruning(user_id, profile)
            self.last_pruning[user_id] = current_time
    
    async def _perform_conversation_pruning(self, user_id: int, profile: Dict[str, Any]):
        """Perform automatic conversation pruning based on relevance"""
        try:
            # Prune conversation history
            history = await self.get_conversation_history(user_id, limit=self.max_conversation_history)
            
            if len(history) > self.context_window_size:
                # Keep recent conversations and high-relevance ones
                recent_conversations = history[-self.context_window_size:]
                
                # For older conversations, only keep high-relevance ones
                older_conversations = history[:-self.context_window_size]
                high_relevance_older = []
                
                for conv in older_conversations:
                    # Estimate relevance based on content (simple heuristic)
                    relevance = self._estimate_conversation_relevance(conv)
                    if relevance >= self.relevance_threshold:
                        high_relevance_older.append(conv)
                
                # Combine recent and high-relevance older conversations
                pruned_history = high_relevance_older + recent_conversations
                
                # Update conversation cache
                user_id_str = str(user_id)
                self.conversation_cache[user_id_str] = pruned_history
                
                # Save pruned history
                history_path = os.path.join(self.data_dir, f"{user_id_str}_history.json")
                try:
                    with open(history_path, 'w', encoding='utf-8') as f:
                        json.dump(pruned_history, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logging.error(f"Error saving pruned history for {user_id}: {e}")
                
                # Record pruning activity
                pruned_count = len(history) - len(pruned_history)
                profile["pruning_history"].append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "conversations_pruned": pruned_count,
                    "conversations_remaining": len(pruned_history)
                })
                
                # Keep only recent pruning history
                profile["pruning_history"] = profile["pruning_history"][-10:]
                
                logging.info(f"Pruned {pruned_count} conversations for user {user_id}")
            
        except Exception as e:
            logging.error(f"Error performing conversation pruning for user {user_id}: {e}")
    
    def _estimate_conversation_relevance(self, conversation: Dict[str, str]) -> float:
        """Estimate conversation relevance using heuristics"""
        user_msg = conversation.get("user", "").lower()
        ai_msg = conversation.get("assistant", "").lower()
        combined = user_msg + " " + ai_msg
        
        relevance_score = 5.0  # Base score
        
        # Boost for aviation-specific content
        aviation_keywords = [
            "aircraft", "flight", "pilot", "aviation", "airport", "weather", "navigation",
            "regulation", "far", "training", "license", "rating", "instrument", "approach"
        ]
        
        keyword_count = sum(1 for keyword in aviation_keywords if keyword in combined)
        relevance_score += min(keyword_count * 0.5, 3.0)  # Max 3 point boost
        
        # Boost for questions (learning opportunities)
        if "?" in user_msg:
            relevance_score += 1.0
        
        # Boost for detailed responses (indicates engagement)
        if len(ai_msg) > 200:
            relevance_score += 0.5
        
        # Reduce for very short exchanges
        if len(combined) < 50:
            relevance_score -= 1.0
        
        return max(1.0, min(10.0, relevance_score))  # Clamp to 1-10 range
    
    async def get_user_context_for_ai(self, user_id: int) -> Dict[str, Any]:
        """
        Get user context formatted for AI model prompting
        Enhanced with context optimization and feedback patterns
        """
        profile = await self.get_profile(user_id)
        
        # Build context dictionary
        context = {}
        
        if profile.get("experience_level"):
            context["experience_level"] = profile["experience_level"]
        
        if profile.get("interests"):
            context["interests"] = profile["interests"][:5]  # Top 5 interests
        
        if profile.get("learning_goals"):
            context["learning_goals"] = profile["learning_goals"][:3]  # Top 3 goals
        
        if profile.get("knowledge_gaps"):
            context["knowledge_gaps"] = profile["knowledge_gaps"][:3]  # Recent gaps
        
        # Add recent conversation context
        recent_topics = [topic["topic"] for topic in profile.get("recent_topics", [])[:3]]
        if recent_topics:
            context["recent_topics"] = recent_topics
        
        # Add conversation style preferences
        context["detail_level"] = profile.get("preferred_detail_level", "medium")
        context["conversation_style"] = profile.get("conversation_style", "friendly")
        
        # Add feedback patterns for better responses
        feedback_patterns = profile.get("feedback_patterns", {})
        if feedback_patterns:
            context["feedback_patterns"] = feedback_patterns
        
        # Add context optimization score
        context["context_quality"] = profile.get("context_optimization_score", 5.0)
        
        return context
    
    async def record_user_feedback(
        self, 
        user_id: int, 
        feedback_type: str, 
        original_response: str, 
        user_correction: str = None,
        feedback_context: Dict[str, Any] = None
    ):
        """
        Record user feedback and corrections for profile improvement
        """
        profile = await self.get_profile(user_id)
        
        # Create feedback record
        feedback_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": feedback_type,  # "correction", "positive", "negative", "clarification"
            "original_response": original_response[:200] + "..." if len(original_response) > 200 else original_response,
            "user_correction": user_correction,
            "context": feedback_context or {}
        }
        
        # Add to correction history
        profile["correction_history"].append(feedback_record)
        
        # Keep only recent corrections
        profile["correction_history"] = profile["correction_history"][-20:]
        
        # Update statistics
        if feedback_type == "correction":
            profile["corrections_provided"] = profile.get("corrections_provided", 0) + 1
        elif feedback_type == "positive":
            profile["helpful_responses_received"] = profile.get("helpful_responses_received", 0) + 1
        
        # Analyze feedback patterns
        await self._analyze_feedback_patterns(profile)
        
        # If this is a correction, boost relevance of related conversations
        if feedback_type == "correction" and user_correction:
            await self._boost_correction_relevance(user_id, profile, user_correction)
        
        # Save updated profile
        await self._save_profile(user_id, profile)
        
        logging.info(f"Recorded {feedback_type} feedback for user {user_id}")
    
    async def _analyze_feedback_patterns(self, profile: Dict[str, Any]):
        """Analyze user feedback patterns to improve future responses"""
        corrections = profile.get("correction_history", [])
        
        if len(corrections) < 3:
            return  # Need at least 3 corrections to identify patterns
        
        patterns = {}
        
        # Analyze correction types
        correction_types = {}
        for correction in corrections[-10:]:  # Last 10 corrections
            correction_type = correction.get("type", "unknown")
            correction_types[correction_type] = correction_types.get(correction_type, 0) + 1
        
        patterns["correction_frequency"] = correction_types
        
        # Analyze common correction topics
        correction_topics = {}
        for correction in corrections[-10:]:
            context = correction.get("context", {})
            topic = context.get("topic", "general")
            correction_topics[topic] = correction_topics.get(topic, 0) + 1
        
        patterns["problematic_topics"] = correction_topics
        
        # Analyze user preferences from corrections
        preferences = {}
        for correction in corrections[-5:]:  # Recent corrections
            user_correction = correction.get("user_correction", "")
            if user_correction:
                # Simple analysis of correction content
                if "more detail" in user_correction.lower() or "explain" in user_correction.lower():
                    preferences["prefers_detailed"] = preferences.get("prefers_detailed", 0) + 1
                elif "simpler" in user_correction.lower() or "basic" in user_correction.lower():
                    preferences["prefers_simple"] = preferences.get("prefers_simple", 0) + 1
        
        patterns["response_preferences"] = preferences
        
        # Update profile with patterns
        profile["feedback_patterns"] = patterns
    
    async def _boost_correction_relevance(
        self, 
        user_id: int, 
        profile: Dict[str, Any], 
        correction_text: str
    ):
        """Boost relevance of conversations related to user corrections"""
        # Find conversations related to the correction
        correction_lower = correction_text.lower()
        
        for conv in profile.get("important_conversations", []):
            conv_summary = conv.get("summary", "").lower()
            
            # Simple similarity check
            common_words = set(correction_lower.split()) & set(conv_summary.split())
            if len(common_words) >= 2:  # At least 2 common words
                # Boost relevance score
                original_score = conv.get("relevance_score", 5)
                boosted_score = min(10, original_score + self.feedback_weight)
                conv["relevance_score"] = boosted_score
                conv["feedback_boosted"] = True
                conv["boost_timestamp"] = datetime.utcnow().isoformat()
    
    async def get_feedback_summary(self, user_id: int) -> Dict[str, Any]:
        """Get a summary of user feedback patterns"""
        profile = await self.get_profile(user_id)
        
        corrections = profile.get("correction_history", [])
        patterns = profile.get("feedback_patterns", {})
        
        return {
            "total_corrections": len(corrections),
            "corrections_provided": profile.get("corrections_provided", 0),
            "helpful_responses": profile.get("helpful_responses_received", 0),
            "feedback_patterns": patterns,
            "recent_corrections": corrections[-5:] if corrections else [],
            "context_optimization_score": profile.get("context_optimization_score", 5.0)
        }
    
    async def get_conversation_history(self, user_id: int, limit: int = 5) -> List[Dict[str, str]]:
        """Get recent conversation history for context"""
        user_id_str = str(user_id)
        
        # Check cache
        if user_id_str in self.conversation_cache:
            return self.conversation_cache[user_id_str][-limit:]
        
        # Load from file
        history_path = os.path.join(self.data_dir, f"{user_id_str}_history.json")
        
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                self.conversation_cache[user_id_str] = history
                return history[-limit:]
            except Exception as e:
                logging.error(f"Error loading conversation history for {user_id}: {e}")
        
        return []
    
    async def add_conversation_exchange(
        self, 
        user_id: int, 
        user_message: str, 
        ai_response: str
    ):
        """Add a conversation exchange to history"""
        user_id_str = str(user_id)
        
        # Get current history
        history = await self.get_conversation_history(user_id, limit=self.max_conversation_history)
        
        # Add new exchange
        exchange = {
            "timestamp": datetime.utcnow().isoformat(),
            "user": user_message,
            "assistant": ai_response
        }
        
        history.append(exchange)
        
        # Keep only recent history
        history = history[-self.max_conversation_history:]
        
        # Update cache
        self.conversation_cache[user_id_str] = history
        
        # Save to file
        history_path = os.path.join(self.data_dir, f"{user_id_str}_history.json")
        try:
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving conversation history for {user_id}: {e}")
    
    async def _save_profile(self, user_id: int, profile: Dict[str, Any]):
        """Save user profile to file"""
        profile_path = os.path.join(self.data_dir, f"{user_id}.json")
        
        try:
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving profile for {user_id}: {e}")
    
    async def cleanup_old_data(self):
        """Clean up old conversation data and low-relevance memories"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.memory_retention_days)
        
        for user_id_str in self.profiles_cache:
            profile = self.profiles_cache[user_id_str]
            
            # Clean old important conversations
            profile["important_conversations"] = [
                conv for conv in profile.get("important_conversations", [])
                if datetime.fromisoformat(conv["timestamp"]) > cutoff_date
            ]
            
            # Clean old recent topics
            profile["recent_topics"] = [
                topic for topic in profile.get("recent_topics", [])
                if datetime.fromisoformat(topic["timestamp"]) > cutoff_date
            ]
            
            # Clean old correction history
            profile["correction_history"] = [
                correction for correction in profile.get("correction_history", [])
                if datetime.fromisoformat(correction["timestamp"]) > cutoff_date
            ]
            
            # Clean old relevance scores
            profile["conversation_relevance_scores"] = [
                score for score in profile.get("conversation_relevance_scores", [])
                if datetime.fromisoformat(score["timestamp"]) > cutoff_date
            ]
            
            # Clean old pruning history
            profile["pruning_history"] = [
                prune for prune in profile.get("pruning_history", [])
                if datetime.fromisoformat(prune["timestamp"]) > cutoff_date
            ]
            
            # Save cleaned profile
            await self._save_profile(int(user_id_str), profile)
    
    async def optimize_all_user_contexts(self):
        """Optimize contexts for all users (maintenance operation)"""
        for user_id_str in self.profiles_cache:
            user_id = int(user_id_str)
            profile = self.profiles_cache[user_id_str]
            await self._optimize_user_context(user_id, profile)
            await self._save_profile(user_id, profile)
        
        logging.info(f"Optimized contexts for {len(self.profiles_cache)} users")
    
    async def get_memory_analytics(self) -> Dict[str, Any]:
        """Get analytics about memory system performance"""
        total_profiles = len(self.profiles_cache)
        total_conversations = 0
        total_corrections = 0
        avg_relevance_scores = []
        context_optimization_scores = []
        
        for profile in self.profiles_cache.values():
            total_conversations += len(profile.get("important_conversations", []))
            total_corrections += len(profile.get("correction_history", []))
            
            relevance_scores = [score["score"] for score in profile.get("conversation_relevance_scores", [])]
            if relevance_scores:
                avg_relevance_scores.extend(relevance_scores)
            
            context_score = profile.get("context_optimization_score", 0)
            if context_score > 0:
                context_optimization_scores.append(context_score)
        
        return {
            "total_profiles": total_profiles,
            "total_important_conversations": total_conversations,
            "total_corrections": total_corrections,
            "average_relevance_score": sum(avg_relevance_scores) / len(avg_relevance_scores) if avg_relevance_scores else 0,
            "average_context_optimization": sum(context_optimization_scores) / len(context_optimization_scores) if context_optimization_scores else 0,
            "memory_retention_days": self.memory_retention_days,
            "relevance_threshold": self.relevance_threshold,
            "auto_prune_interval_hours": self.auto_prune_interval / 3600
        }
    
    def get_profile_stats(self) -> Dict[str, Any]:
        """Get statistics about the profile system"""
        return {
            "total_profiles": len(self.profiles_cache),
            "cached_conversations": len(self.conversation_cache),
            "data_directory": self.data_dir,
            "retention_days": self.memory_retention_days,
            "relevance_threshold": self.relevance_threshold,
            "context_optimization_threshold": self.context_optimization_threshold,
            "auto_prune_interval_hours": self.auto_prune_interval / 3600,
            "important_memory_limit": self.important_memory_limit,
            "feedback_weight": self.feedback_weight
        }