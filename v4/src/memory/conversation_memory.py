"""
V4 Conversation Memory Management
Structured conversation storage with context retrieval and threading
Privacy-compliant data retention and cleanup
"""

import json
import os
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import logging
import hashlib
import sqlite3
from dataclasses import dataclass, asdict
from enum import Enum

class ConversationType(Enum):
    """Types of conversations for categorization"""
    DIRECT_MESSAGE = "direct_message"
    GUILD_MESSAGE = "guild_message"
    THREAD_MESSAGE = "thread_message"
    REACTION_INTERACTION = "reaction_interaction"

class ConversationContext(Enum):
    """Context types for conversation threading"""
    STANDALONE = "standalone"
    THREAD_CONTINUATION = "thread_continuation"
    TOPIC_CONTINUATION = "topic_continuation"
    FOLLOW_UP = "follow_up"

@dataclass
class ConversationExchange:
    """Individual conversation exchange data model"""
    id: str
    user_id: int
    guild_id: Optional[int]
    channel_id: int
    thread_id: Optional[int]
    timestamp: datetime
    conversation_type: ConversationType
    context_type: ConversationContext
    
    # Message content
    user_message: str
    ai_response: str
    
    # Context and metadata
    topic: Optional[str]
    aviation_category: Optional[str]
    relevance_score: float
    context_hash: str
    
    # Threading and relationships
    parent_exchange_id: Optional[str]
    related_exchange_ids: List[str]
    
    # Privacy and retention
    retention_category: str  # "essential", "important", "standard", "temporary"
    expires_at: Optional[datetime]
    
    # Analytics
    user_satisfaction: Optional[str]  # "positive", "negative", "neutral", "unknown"
    correction_applied: bool
    feedback_received: bool

class ConversationMemoryManager:
    """
    Manages structured conversation storage with context retrieval and threading
    Implements privacy-compliant data retention and cleanup
    """
    
    def __init__(self, data_dir: str = "data/conversations", ai_orchestrator=None):
        self.data_dir = data_dir
        self.ai_orchestrator = ai_orchestrator
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Initialize SQLite database for structured storage
        self.db_path = os.path.join(data_dir, "conversations.db")
        self._init_database()
        
        # Memory settings
        self.max_context_exchanges = 10  # Max exchanges to include in context
        self.thread_context_limit = 20  # Max exchanges per thread context
        self.topic_similarity_threshold = 0.7  # Threshold for topic continuation
        
        # Retention settings
        self.retention_policies = {
            "essential": timedelta(days=365),  # User corrections, important feedback
            "important": timedelta(days=180),  # High relevance conversations
            "standard": timedelta(days=90),    # Regular conversations
            "temporary": timedelta(days=30)    # Low relevance, casual exchanges
        }
        
        # Privacy settings
        self.anonymize_after_days = 30  # Anonymize old conversations
        self.hard_delete_after_days = 400  # Hard delete very old data
        
        # Context caching
        self.context_cache = {}  # user_id -> recent context
        self.thread_cache = {}   # thread_id -> thread context
    
    async def initialize(self):
        """Initialize the conversation memory manager"""
        # Perform any async initialization tasks
        logging.info("ConversationMemoryManager initialized successfully")
        return True
        
    def _init_database(self):
        """Initialize SQLite database with conversation schema"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        guild_id INTEGER,
                        channel_id INTEGER NOT NULL,
                        thread_id INTEGER,
                        timestamp TEXT NOT NULL,
                        conversation_type TEXT NOT NULL,
                        context_type TEXT NOT NULL,
                        user_message TEXT NOT NULL,
                        ai_response TEXT NOT NULL,
                        topic TEXT,
                        aviation_category TEXT,
                        relevance_score REAL NOT NULL,
                        context_hash TEXT NOT NULL,
                        parent_exchange_id TEXT,
                        related_exchange_ids TEXT,
                        retention_category TEXT NOT NULL,
                        expires_at TEXT,
                        user_satisfaction TEXT,
                        correction_applied BOOLEAN DEFAULT FALSE,
                        feedback_received BOOLEAN DEFAULT FALSE,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                
                # Create indexes for efficient querying
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON conversations(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON conversations(timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_thread_id ON conversations(thread_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_topic ON conversations(topic)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_context_hash ON conversations(context_hash)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_expires_at ON conversations(expires_at)")
                
                conn.commit()
                
        except Exception as e:
            logging.error(f"Error initializing conversation database: {e}")
            raise
    
    async def store_conversation_exchange(
        self,
        user_id: int,
        guild_id: Optional[int],
        channel_id: int,
        thread_id: Optional[int],
        user_message: str,
        ai_response: str,
        conversation_type: ConversationType = ConversationType.GUILD_MESSAGE,
        topic: Optional[str] = None,
        aviation_category: Optional[str] = None,
        relevance_score: Optional[float] = None,
        parent_exchange_id: Optional[str] = None
    ) -> str:
        """Store a conversation exchange with full context"""
        
        # Generate unique ID
        exchange_id = self._generate_exchange_id(user_id, user_message, ai_response)
        
        # Determine context type
        context_type = await self._determine_context_type(
            user_id, thread_id, topic, user_message, parent_exchange_id
        )
        
        # Calculate relevance score if not provided
        if relevance_score is None:
            relevance_score = await self._calculate_relevance_score(
                user_message, ai_response, aviation_category
            )
        
        # Determine retention category
        retention_category = self._determine_retention_category(
            relevance_score, context_type, aviation_category
        )
        
        # Calculate expiration date
        expires_at = datetime.utcnow() + self.retention_policies[retention_category]
        
        # Create conversation exchange
        exchange = ConversationExchange(
            id=exchange_id,
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            thread_id=thread_id,
            timestamp=datetime.utcnow(),
            conversation_type=conversation_type,
            context_type=context_type,
            user_message=user_message,
            ai_response=ai_response,
            topic=topic or await self._extract_topic(user_message, ai_response),
            aviation_category=aviation_category or await self._categorize_aviation_content(user_message, ai_response),
            relevance_score=relevance_score,
            context_hash=self._generate_context_hash(user_message, ai_response),
            parent_exchange_id=parent_exchange_id,
            related_exchange_ids=[],
            retention_category=retention_category,
            expires_at=expires_at,
            user_satisfaction=None,
            correction_applied=False,
            feedback_received=False
        )
        
        # Store in database
        await self._store_exchange_in_db(exchange)
        
        # Update context caches
        await self._update_context_caches(exchange)
        
        # Find and link related exchanges
        await self._link_related_exchanges(exchange)
        
        logging.info(f"Stored conversation exchange {exchange_id} for user {user_id}")
        return exchange_id
    
    async def get_conversation_context(
        self,
        user_id: int,
        thread_id: Optional[int] = None,
        topic: Optional[str] = None,
        limit: int = 10
    ) -> List[ConversationExchange]:
        """Retrieve conversation context for AI processing"""
        
        # Check cache first
        cache_key = f"{user_id}_{thread_id}_{topic}"
        if cache_key in self.context_cache:
            cached_context = self.context_cache[cache_key]
            if len(cached_context) <= limit:
                return cached_context
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Build query based on context requirements
                if thread_id:
                    # Thread-specific context
                    query = """
                        SELECT * FROM conversations 
                        WHERE user_id = ? AND thread_id = ?
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """
                    params = (user_id, thread_id, limit)
                elif topic:
                    # Topic-based context
                    query = """
                        SELECT * FROM conversations 
                        WHERE user_id = ? AND topic = ?
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """
                    params = (user_id, topic, limit)
                else:
                    # General user context
                    query = """
                        SELECT * FROM conversations 
                        WHERE user_id = ?
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """
                    params = (user_id, limit)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to ConversationExchange objects
                exchanges = []
                for row in rows:
                    exchange = self._row_to_exchange(row)
                    exchanges.append(exchange)
                
                # Cache the result
                self.context_cache[cache_key] = exchanges
                
                return list(reversed(exchanges))  # Return in chronological order
                
        except Exception as e:
            logging.error(f"Error retrieving conversation context for user {user_id}: {e}")
            return []
    
    async def get_thread_conversation(self, thread_id: int, limit: int = 50) -> List[ConversationExchange]:
        """Get complete thread conversation history"""
        
        # Check thread cache
        if thread_id in self.thread_cache:
            cached_thread = self.thread_cache[thread_id]
            if len(cached_thread) <= limit:
                return cached_thread
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                query = """
                    SELECT * FROM conversations 
                    WHERE thread_id = ?
                    ORDER BY timestamp ASC 
                    LIMIT ?
                """
                
                cursor = conn.execute(query, (thread_id, limit))
                rows = cursor.fetchall()
                
                exchanges = []
                for row in rows:
                    exchange = self._row_to_exchange(row)
                    exchanges.append(exchange)
                
                # Cache the thread
                self.thread_cache[thread_id] = exchanges
                
                return exchanges
                
        except Exception as e:
            logging.error(f"Error retrieving thread conversation {thread_id}: {e}")
            return []
    
    async def update_exchange_feedback(
        self,
        exchange_id: str,
        user_satisfaction: Optional[str] = None,
        correction_applied: bool = False,
        feedback_received: bool = False
    ):
        """Update exchange with user feedback"""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                updates = []
                params = []
                
                if user_satisfaction:
                    updates.append("user_satisfaction = ?")
                    params.append(user_satisfaction)
                
                if correction_applied:
                    updates.append("correction_applied = ?")
                    params.append(correction_applied)
                
                if feedback_received:
                    updates.append("feedback_received = ?")
                    params.append(feedback_received)
                
                if updates:
                    updates.append("updated_at = ?")
                    params.append(datetime.utcnow().isoformat())
                    params.append(exchange_id)
                    
                    query = f"""
                        UPDATE conversations 
                        SET {', '.join(updates)}
                        WHERE id = ?
                    """
                    
                    conn.execute(query, params)
                    conn.commit()
                    
                    # If correction was applied, upgrade retention category
                    if correction_applied:
                        await self._upgrade_retention_category(exchange_id, "essential")
                    
                    logging.info(f"Updated feedback for exchange {exchange_id}")
                
        except Exception as e:
            logging.error(f"Error updating exchange feedback {exchange_id}: {e}")
    
    async def search_conversations(
        self,
        user_id: Optional[int] = None,
        topic: Optional[str] = None,
        aviation_category: Optional[str] = None,
        min_relevance_score: float = 0.0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[ConversationExchange]:
        """Search conversations with flexible criteria"""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Build dynamic query
                conditions = []
                params = []
                
                if user_id:
                    conditions.append("user_id = ?")
                    params.append(user_id)
                
                if topic:
                    conditions.append("topic LIKE ?")
                    params.append(f"%{topic}%")
                
                if aviation_category:
                    conditions.append("aviation_category = ?")
                    params.append(aviation_category)
                
                if min_relevance_score > 0:
                    conditions.append("relevance_score >= ?")
                    params.append(min_relevance_score)
                
                if start_date:
                    conditions.append("timestamp >= ?")
                    params.append(start_date.isoformat())
                
                if end_date:
                    conditions.append("timestamp <= ?")
                    params.append(end_date.isoformat())
                
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                
                query = f"""
                    SELECT * FROM conversations 
                    WHERE {where_clause}
                    ORDER BY relevance_score DESC, timestamp DESC 
                    LIMIT ?
                """
                params.append(limit)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                exchanges = []
                for row in rows:
                    exchange = self._row_to_exchange(row)
                    exchanges.append(exchange)
                
                return exchanges
                
        except Exception as e:
            logging.error(f"Error searching conversations: {e}")
            return []
    
    async def cleanup_expired_conversations(self):
        """Clean up expired conversations based on retention policies"""
        
        try:
            current_time = datetime.utcnow()
            
            with sqlite3.connect(self.db_path) as conn:
                # Find expired conversations
                cursor = conn.execute("""
                    SELECT id, retention_category, expires_at 
                    FROM conversations 
                    WHERE expires_at < ?
                """, (current_time.isoformat(),))
                
                expired_exchanges = cursor.fetchall()
                
                if expired_exchanges:
                    # Delete expired conversations
                    expired_ids = [row[0] for row in expired_exchanges]
                    placeholders = ','.join(['?'] * len(expired_ids))
                    
                    conn.execute(f"""
                        DELETE FROM conversations 
                        WHERE id IN ({placeholders})
                    """, expired_ids)
                    
                    conn.commit()
                    
                    logging.info(f"Cleaned up {len(expired_exchanges)} expired conversations")
                
                # Anonymize old conversations (privacy compliance)
                anonymize_cutoff = current_time - timedelta(days=self.anonymize_after_days)
                
                conn.execute("""
                    UPDATE conversations 
                    SET user_message = '[ANONYMIZED]', 
                        ai_response = '[ANONYMIZED]',
                        updated_at = ?
                    WHERE timestamp < ? AND user_message != '[ANONYMIZED]'
                """, (current_time.isoformat(), anonymize_cutoff.isoformat()))
                
                conn.commit()
                
        except Exception as e:
            logging.error(f"Error cleaning up expired conversations: {e}")
    
    async def get_conversation_analytics(self) -> Dict[str, Any]:
        """Get analytics about conversation storage and patterns"""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Total conversations
                total_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
                
                # Conversations by type
                type_counts = {}
                cursor = conn.execute("""
                    SELECT conversation_type, COUNT(*) 
                    FROM conversations 
                    GROUP BY conversation_type
                """)
                for row in cursor.fetchall():
                    type_counts[row[0]] = row[1]
                
                # Conversations by retention category
                retention_counts = {}
                cursor = conn.execute("""
                    SELECT retention_category, COUNT(*) 
                    FROM conversations 
                    GROUP BY retention_category
                """)
                for row in cursor.fetchall():
                    retention_counts[row[0]] = row[1]
                
                # Average relevance score
                avg_relevance = conn.execute("""
                    SELECT AVG(relevance_score) FROM conversations
                """).fetchone()[0] or 0
                
                # Conversations with feedback
                feedback_count = conn.execute("""
                    SELECT COUNT(*) FROM conversations 
                    WHERE feedback_received = TRUE
                """).fetchone()[0]
                
                # Conversations with corrections
                correction_count = conn.execute("""
                    SELECT COUNT(*) FROM conversations 
                    WHERE correction_applied = TRUE
                """).fetchone()[0]
                
                # Top aviation categories
                category_counts = {}
                cursor = conn.execute("""
                    SELECT aviation_category, COUNT(*) 
                    FROM conversations 
                    WHERE aviation_category IS NOT NULL
                    GROUP BY aviation_category 
                    ORDER BY COUNT(*) DESC 
                    LIMIT 10
                """)
                for row in cursor.fetchall():
                    category_counts[row[0]] = row[1]
                
                return {
                    "total_conversations": total_count,
                    "conversations_by_type": type_counts,
                    "conversations_by_retention": retention_counts,
                    "average_relevance_score": round(avg_relevance, 2),
                    "conversations_with_feedback": feedback_count,
                    "conversations_with_corrections": correction_count,
                    "top_aviation_categories": category_counts,
                    "retention_policies": {k: v.days for k, v in self.retention_policies.items()},
                    "anonymize_after_days": self.anonymize_after_days,
                    "hard_delete_after_days": self.hard_delete_after_days
                }
                
        except Exception as e:
            logging.error(f"Error getting conversation analytics: {e}")
            return {}
    
    async def delete_user_conversations(self, user_id: int) -> int:
        """Delete all conversations for a user (privacy compliance)"""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Count conversations to be deleted
                count = conn.execute("""
                    SELECT COUNT(*) FROM conversations WHERE user_id = ?
                """, (user_id,)).fetchone()[0]
                
                # Delete conversations
                conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
                conn.commit()
                
                # Clear caches
                self._clear_user_caches(user_id)
                
                logging.info(f"Deleted {count} conversations for user {user_id}")
                return count
                
        except Exception as e:
            logging.error(f"Error deleting conversations for user {user_id}: {e}")
            return 0
    
    # Helper methods
    
    def _generate_exchange_id(self, user_id: int, user_message: str, ai_response: str) -> str:
        """Generate unique exchange ID"""
        content = f"{user_id}_{user_message[:100]}_{ai_response[:100]}_{datetime.utcnow().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _generate_context_hash(self, user_message: str, ai_response: str) -> str:
        """Generate context hash for deduplication"""
        content = f"{user_message}_{ai_response}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    async def _determine_context_type(
        self,
        user_id: int,
        thread_id: Optional[int],
        topic: Optional[str],
        user_message: str,
        parent_exchange_id: Optional[str]
    ) -> ConversationContext:
        """Determine the context type for the conversation"""
        
        if parent_exchange_id:
            return ConversationContext.FOLLOW_UP
        
        if thread_id:
            # Check if this continues an existing thread
            thread_history = await self.get_thread_conversation(thread_id, limit=5)
            if thread_history:
                return ConversationContext.THREAD_CONTINUATION
        
        if topic:
            # Check if this continues a topic
            recent_context = await self.get_conversation_context(user_id, topic=topic, limit=3)
            if recent_context:
                return ConversationContext.TOPIC_CONTINUATION
        
        return ConversationContext.STANDALONE
    
    async def _calculate_relevance_score(
        self,
        user_message: str,
        ai_response: str,
        aviation_category: Optional[str]
    ) -> float:
        """Calculate relevance score for the conversation"""
        
        # Base score
        score = 5.0
        
        # Aviation content boost
        if aviation_category:
            score += 2.0
        
        # Question boost (learning opportunity)
        if "?" in user_message:
            score += 1.0
        
        # Detailed response boost
        if len(ai_response) > 200:
            score += 1.0
        
        # Technical content boost
        technical_keywords = [
            "regulation", "far", "aircraft", "navigation", "weather", "approach",
            "departure", "instrument", "visual", "emergency", "procedure"
        ]
        
        combined_text = (user_message + " " + ai_response).lower()
        keyword_count = sum(1 for keyword in technical_keywords if keyword in combined_text)
        score += min(keyword_count * 0.5, 2.0)
        
        # Reduce for very short exchanges
        if len(user_message + ai_response) < 50:
            score -= 1.0
        
        return max(1.0, min(10.0, score))
    
    def _determine_retention_category(
        self,
        relevance_score: float,
        context_type: ConversationContext,
        aviation_category: Optional[str]
    ) -> str:
        """Determine retention category based on conversation characteristics"""
        
        # Essential: High relevance or important context
        if relevance_score >= 8.0 or context_type == ConversationContext.FOLLOW_UP:
            return "essential"
        
        # Important: Good relevance or aviation-specific
        if relevance_score >= 6.0 or aviation_category:
            return "important"
        
        # Standard: Medium relevance
        if relevance_score >= 4.0:
            return "standard"
        
        # Temporary: Low relevance
        return "temporary"
    
    async def _extract_topic(self, user_message: str, ai_response: str) -> Optional[str]:
        """Extract topic from conversation content"""
        
        # Aviation topic keywords
        aviation_topics = {
            "weather": ["weather", "metar", "taf", "wind", "visibility", "ceiling"],
            "navigation": ["navigation", "gps", "vor", "ils", "approach", "departure"],
            "aircraft": ["cessna", "piper", "boeing", "airbus", "helicopter", "aircraft"],
            "regulations": ["far", "regulation", "rule", "legal", "requirement", "faa"],
            "training": ["training", "lesson", "instructor", "student", "practice"],
            "flight_planning": ["flight plan", "route", "fuel", "weight", "balance"],
            "emergency": ["emergency", "malfunction", "failure", "abort", "divert"],
            "airports": ["airport", "runway", "taxiway", "tower", "ground", "atc"],
            "licenses": ["license", "rating", "certificate", "private", "commercial"]
        }
        
        combined_text = (user_message + " " + ai_response).lower()
        
        for topic, keywords in aviation_topics.items():
            if any(keyword in combined_text for keyword in keywords):
                return topic
        
        return "general_aviation"
    
    async def _categorize_aviation_content(self, user_message: str, ai_response: str) -> Optional[str]:
        """Categorize aviation content for better organization"""
        
        combined_text = (user_message + " " + ai_response).lower()
        
        categories = {
            "weather_interpretation": ["metar", "taf", "decode", "interpret", "weather"],
            "flight_training": ["solo", "dual", "instructor", "lesson", "maneuver", "checkride"],
            "aircraft_systems": ["engine", "electrical", "hydraulic", "avionics", "system"],
            "navigation_procedures": ["approach", "departure", "hold", "intercept", "radial"],
            "emergency_procedures": ["engine failure", "electrical failure", "lost comm", "emergency"],
            "regulations_compliance": ["far", "regulation", "legal", "violation", "compliance"],
            "flight_planning": ["flight plan", "route", "fuel", "weight", "balance", "performance"],
            "airport_operations": ["airport", "runway", "taxiway", "tower", "ground", "clearance"]
        }
        
        for category, keywords in categories.items():
            if any(keyword in combined_text for keyword in keywords):
                return category
        
        return None
    
    async def _store_exchange_in_db(self, exchange: ConversationExchange):
        """Store conversation exchange in database"""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO conversations (
                        id, user_id, guild_id, channel_id, thread_id, timestamp,
                        conversation_type, context_type, user_message, ai_response,
                        topic, aviation_category, relevance_score, context_hash,
                        parent_exchange_id, related_exchange_ids, retention_category,
                        expires_at, user_satisfaction, correction_applied,
                        feedback_received, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    exchange.id, exchange.user_id, exchange.guild_id, exchange.channel_id,
                    exchange.thread_id, exchange.timestamp.isoformat(),
                    exchange.conversation_type.value, exchange.context_type.value,
                    exchange.user_message, exchange.ai_response, exchange.topic,
                    exchange.aviation_category, exchange.relevance_score, exchange.context_hash,
                    exchange.parent_exchange_id, json.dumps(exchange.related_exchange_ids),
                    exchange.retention_category, exchange.expires_at.isoformat() if exchange.expires_at else None,
                    exchange.user_satisfaction, exchange.correction_applied,
                    exchange.feedback_received, datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat()
                ))
                conn.commit()
                
        except Exception as e:
            logging.error(f"Error storing exchange in database: {e}")
            raise
    
    async def _update_context_caches(self, exchange: ConversationExchange):
        """Update context caches with new exchange"""
        
        # Update user context cache
        user_cache_key = f"{exchange.user_id}__"
        if user_cache_key in self.context_cache:
            self.context_cache[user_cache_key].append(exchange)
            # Keep only recent exchanges
            self.context_cache[user_cache_key] = self.context_cache[user_cache_key][-self.max_context_exchanges:]
        
        # Update thread cache
        if exchange.thread_id and exchange.thread_id in self.thread_cache:
            self.thread_cache[exchange.thread_id].append(exchange)
            # Keep only recent thread exchanges
            self.thread_cache[exchange.thread_id] = self.thread_cache[exchange.thread_id][-self.thread_context_limit:]
    
    async def _link_related_exchanges(self, exchange: ConversationExchange):
        """Find and link related exchanges"""
        
        # Find exchanges with similar context hash or topic
        related_exchanges = await self.search_conversations(
            user_id=exchange.user_id,
            topic=exchange.topic,
            min_relevance_score=6.0,
            limit=5
        )
        
        # Filter out the current exchange and link others
        related_ids = [ex.id for ex in related_exchanges if ex.id != exchange.id]
        
        if related_ids:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        UPDATE conversations 
                        SET related_exchange_ids = ?, updated_at = ?
                        WHERE id = ?
                    """, (json.dumps(related_ids), datetime.utcnow().isoformat(), exchange.id))
                    conn.commit()
                    
            except Exception as e:
                logging.error(f"Error linking related exchanges: {e}")
    
    async def _upgrade_retention_category(self, exchange_id: str, new_category: str):
        """Upgrade retention category for important exchanges"""
        
        try:
            new_expires_at = datetime.utcnow() + self.retention_policies[new_category]
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE conversations 
                    SET retention_category = ?, expires_at = ?, updated_at = ?
                    WHERE id = ?
                """, (new_category, new_expires_at.isoformat(), datetime.utcnow().isoformat(), exchange_id))
                conn.commit()
                
        except Exception as e:
            logging.error(f"Error upgrading retention category: {e}")
    
    def _row_to_exchange(self, row: sqlite3.Row) -> ConversationExchange:
        """Convert database row to ConversationExchange object"""
        
        return ConversationExchange(
            id=row['id'],
            user_id=row['user_id'],
            guild_id=row['guild_id'],
            channel_id=row['channel_id'],
            thread_id=row['thread_id'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            conversation_type=ConversationType(row['conversation_type']),
            context_type=ConversationContext(row['context_type']),
            user_message=row['user_message'],
            ai_response=row['ai_response'],
            topic=row['topic'],
            aviation_category=row['aviation_category'],
            relevance_score=row['relevance_score'],
            context_hash=row['context_hash'],
            parent_exchange_id=row['parent_exchange_id'],
            related_exchange_ids=json.loads(row['related_exchange_ids']) if row['related_exchange_ids'] else [],
            retention_category=row['retention_category'],
            expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
            user_satisfaction=row['user_satisfaction'],
            correction_applied=bool(row['correction_applied']),
            feedback_received=bool(row['feedback_received'])
        )
    
    def _clear_user_caches(self, user_id: int):
        """Clear caches for a specific user"""
        
        # Clear context cache entries for this user
        keys_to_remove = [key for key in self.context_cache.keys() if key.startswith(f"{user_id}_")]
        for key in keys_to_remove:
            del self.context_cache[key]