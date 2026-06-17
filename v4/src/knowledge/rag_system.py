"""
V4 RAG System - Retrieval-Augmented Generation
Provides aviation knowledge retrieval with vector similarity search
"""

import numpy as np
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import os
from dataclasses import dataclass, asdict
from sentence_transformers import SentenceTransformer
import sqlite3
import pickle

from ..bot.error_handler import ErrorHandler, ErrorSeverity, handle_errors

@dataclass
class AviationKnowledge:
    """Aviation knowledge item with metadata"""
    id: str
    title: str
    content: str
    source: str
    category: str  # regulation, aircraft, weather, procedure, airport
    last_updated: str
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None

class RAGSystem:
    """
    Retrieval-Augmented Generation system for aviation knowledge
    Uses vector similarity search to find relevant information
    """
    
    def __init__(self, data_dir: str = "data/knowledge", error_handler: Optional[ErrorHandler] = None):
        self.data_dir = data_dir
        self.db_path = os.path.join(data_dir, "aviation_knowledge.db")
        self.embeddings_path = os.path.join(data_dir, "embeddings.pkl")
        self.error_handler = error_handler or ErrorHandler()
        
        # Embedding model for similarity search
        self.embedding_model = None
        self.knowledge_items = {}
        self.embeddings_matrix = None
        self.is_ready = False
        
        # Search settings
        self.max_results = 5
        self.similarity_threshold = 0.3
        self.context_window = 2000  # Max characters for context
        
        # Error handling settings
        self.max_retries = 2
        self.retry_delay = 1.0
        
        # System health tracking
        self.system_health = {
            "embedding_model_loaded": False,
            "database_accessible": False,
            "knowledge_items_loaded": False,
            "last_health_check": datetime.utcnow()
        }
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
    async def initialize(self):
        """Initialize the RAG system"""
        logging.info("Initializing RAG system...")
        
        try:
            # Load embedding model with retry
            await self._load_embedding_model_with_retry()
            
            # Initialize database with error handling
            await self._init_database_safe()
            
            # Load existing knowledge and embeddings
            await self._load_knowledge_base_safe()
            
            # If no knowledge exists, load default aviation data
            if not self.knowledge_items:
                await self._load_default_aviation_data_safe()
            
            # Update system health
            await self._check_system_health()
            
            self.is_ready = True
            logging.info(f"RAG system initialized with {len(self.knowledge_items)} knowledge items")
            
        except Exception as e:
            await self.error_handler.handle_error(
                e,
                {"data_dir": self.data_dir},
                "rag_system",
                severity=ErrorSeverity.CRITICAL
            )
            self.is_ready = False
            raise
    
    async def _init_database(self):
        """Initialize SQLite database for knowledge storage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS aviation_knowledge (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                metadata TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    async def _load_knowledge_base(self):
        """Load knowledge items from database and embeddings from file"""
        try:
            # Load knowledge items from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM aviation_knowledge')
            rows = cursor.fetchall()
            
            for row in rows:
                knowledge_item = AviationKnowledge(
                    id=row[0],
                    title=row[1],
                    content=row[2],
                    source=row[3],
                    category=row[4],
                    last_updated=row[5],
                    metadata=json.loads(row[6]) if row[6] else None
                )
                self.knowledge_items[knowledge_item.id] = knowledge_item
            
            conn.close()
            
            # Load embeddings if they exist
            if os.path.exists(self.embeddings_path):
                with open(self.embeddings_path, 'rb') as f:
                    embeddings_data = pickle.load(f)
                    self.embeddings_matrix = embeddings_data['embeddings']
                    
                    # Assign embeddings to knowledge items
                    for i, item_id in enumerate(embeddings_data['item_ids']):
                        if item_id in self.knowledge_items:
                            self.knowledge_items[item_id].embedding = self.embeddings_matrix[i].tolist()
            
            logging.info(f"Loaded {len(self.knowledge_items)} knowledge items")
            
        except Exception as e:
            logging.error(f"Error loading knowledge base: {e}")
    
    async def _load_default_aviation_data(self):
        """Load default aviation knowledge data"""
        logging.info("Loading default aviation knowledge...")
        
        default_knowledge = [
            {
                "id": "far_91_general",
                "title": "FAR Part 91 - General Operating Rules",
                "content": "Part 91 prescribes rules governing the operation of aircraft within the United States. It covers general operating and flight rules, equipment requirements, and maintenance requirements for most civil aircraft operations.",
                "source": "FAA Regulations",
                "category": "regulation",
                "metadata": {"regulation_part": "91", "authority": "FAA"}
            },
            {
                "id": "cessna_172_specs",
                "title": "Cessna 172 Specifications",
                "content": "The Cessna 172 is a four-seat, single-engine, high-wing aircraft. Maximum speed: 140 knots, Service ceiling: 14,000 feet, Range: 640 nautical miles, Engine: Lycoming IO-360-L2A producing 180 horsepower.",
                "source": "Aircraft Database",
                "category": "aircraft",
                "metadata": {"manufacturer": "Cessna", "model": "172", "category": "single_engine"}
            },
            {
                "id": "metar_basics",
                "title": "METAR Weather Reports",
                "content": "METAR is a format for reporting weather information. A typical METAR includes station identifier, observation time, wind, visibility, weather phenomena, clouds, temperature, dewpoint, and altimeter setting.",
                "source": "Weather Knowledge Base",
                "category": "weather",
                "metadata": {"type": "weather_report", "format": "METAR"}
            },
            {
                "id": "vfr_minimums",
                "title": "VFR Weather Minimums",
                "content": "Visual Flight Rules (VFR) weather minimums vary by airspace. In Class E airspace below 10,000 feet: 3 statute miles visibility, 500 feet below clouds, 1,000 feet above clouds, 2,000 feet horizontal from clouds.",
                "source": "FAA Regulations",
                "category": "regulation",
                "metadata": {"flight_rules": "VFR", "airspace": "Class E"}
            },
            {
                "id": "pattern_procedures",
                "title": "Airport Traffic Pattern Procedures",
                "content": "Standard traffic pattern is flown at 1,000 feet AGL for single-engine aircraft. Pattern consists of upwind, crosswind, downwind, base, and final legs. Left traffic is standard unless otherwise indicated.",
                "source": "AIM",
                "category": "procedure",
                "metadata": {"type": "traffic_pattern", "altitude": "1000_agl"}
            }
        ]
        
        for item_data in default_knowledge:
            knowledge_item = AviationKnowledge(
                id=item_data["id"],
                title=item_data["title"],
                content=item_data["content"],
                source=item_data["source"],
                category=item_data["category"],
                last_updated=datetime.utcnow().isoformat(),
                metadata=item_data.get("metadata")
            )
            
            await self.add_knowledge_item(knowledge_item)
    
    async def retrieve_knowledge(self, query: str, context: Dict[str, Any] = None) -> str:
        """
        Retrieve relevant aviation knowledge for a query
        Returns formatted context string for AI model
        """
        if not self.is_ready:
            return "Knowledge system not ready"
        
        try:
            # Check system health periodically
            await self._check_system_health()
            
            # Get relevant knowledge items with retry
            relevant_items = await self._search_knowledge_with_retry(query, max_results=self.max_results)
            
            if not relevant_items:
                return self._get_fallback_knowledge(query)
            
            # Format knowledge for AI context
            context_parts = []
            total_length = 0
            
            for item, similarity in relevant_items:
                # Create formatted knowledge entry
                entry = f"**{item.title}** (Source: {item.source})\n{item.content}\n"
                
                # Check if adding this entry would exceed context window
                if total_length + len(entry) > self.context_window:
                    break
                
                context_parts.append(entry)
                total_length += len(entry)
            
            return "\n".join(context_parts)
            
        except Exception as e:
            await self.error_handler.handle_error(
                e,
                {"query": query[:100]},
                "rag_system",
                severity=ErrorSeverity.MEDIUM
            )
            return self._get_fallback_knowledge(query)
    
    async def _search_knowledge(self, query: str, max_results: int = 5) -> List[Tuple[AviationKnowledge, float]]:
        """
        Search knowledge base using vector similarity
        Returns list of (knowledge_item, similarity_score) tuples
        """
        if not self.embedding_model or not self.knowledge_items:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query])[0]
            
            # Calculate similarities with all knowledge items
            similarities = []
            
            for item_id, item in self.knowledge_items.items():
                if item.embedding:
                    # Calculate cosine similarity
                    item_embedding = np.array(item.embedding)
                    similarity = np.dot(query_embedding, item_embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(item_embedding)
                    )
                    
                    if similarity >= self.similarity_threshold:
                        similarities.append((item, float(similarity)))
            
            # Sort by similarity and return top results
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:max_results]
            
        except Exception as e:
            logging.error(f"Error searching knowledge: {e}")
            return []
    
    async def search_regulations(self, query: str) -> List[Dict[str, Any]]:
        """Search specifically for aviation regulations"""
        relevant_items = await self._search_knowledge(query)
        
        regulation_results = []
        for item, similarity in relevant_items:
            if item.category == "regulation":
                regulation_results.append({
                    "title": item.title,
                    "content": item.content,
                    "source": item.source,
                    "similarity": similarity,
                    "metadata": item.metadata or {}
                })
        
        return regulation_results
    
    async def get_aircraft_info(self, aircraft_query: str) -> Dict[str, Any]:
        """Get aircraft-specific information"""
        relevant_items = await self._search_knowledge(aircraft_query)
        
        for item, similarity in relevant_items:
            if item.category == "aircraft" and similarity > 0.5:
                return {
                    "title": item.title,
                    "content": item.content,
                    "source": item.source,
                    "similarity": similarity,
                    "metadata": item.metadata or {}
                }
        
        return {}
    
    async def add_knowledge_item(self, knowledge_item: AviationKnowledge):
        """Add a new knowledge item to the database"""
        try:
            # Generate embedding for the content
            if self.embedding_model:
                embedding = self.embedding_model.encode([knowledge_item.content])[0]
                knowledge_item.embedding = embedding.tolist()
            
            # Store in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO aviation_knowledge 
                (id, title, content, source, category, last_updated, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                knowledge_item.id,
                knowledge_item.title,
                knowledge_item.content,
                knowledge_item.source,
                knowledge_item.category,
                knowledge_item.last_updated,
                json.dumps(knowledge_item.metadata) if knowledge_item.metadata else None
            ))
            
            conn.commit()
            conn.close()
            
            # Update in-memory storage
            self.knowledge_items[knowledge_item.id] = knowledge_item
            
            # Update embeddings matrix
            await self._update_embeddings_matrix()
            
            logging.info(f"Added knowledge item: {knowledge_item.title}")
            
        except Exception as e:
            logging.error(f"Error adding knowledge item: {e}")
    
    async def _update_embeddings_matrix(self):
        """Update the embeddings matrix and save to file"""
        try:
            embeddings = []
            item_ids = []
            
            for item_id, item in self.knowledge_items.items():
                if item.embedding:
                    embeddings.append(item.embedding)
                    item_ids.append(item_id)
            
            if embeddings:
                self.embeddings_matrix = np.array(embeddings)
                
                # Save to file
                embeddings_data = {
                    'embeddings': self.embeddings_matrix,
                    'item_ids': item_ids
                }
                
                with open(self.embeddings_path, 'wb') as f:
                    pickle.dump(embeddings_data, f)
                
                logging.info(f"Updated embeddings matrix with {len(embeddings)} items")
            
        except Exception as e:
            logging.error(f"Error updating embeddings matrix: {e}")
    
    async def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base"""
        category_counts = {}
        for item in self.knowledge_items.values():
            category_counts[item.category] = category_counts.get(item.category, 0) + 1
        
        return {
            "total_items": len(self.knowledge_items),
            "categories": category_counts,
            "embedding_model": "all-MiniLM-L6-v2",
            "similarity_threshold": self.similarity_threshold,
            "max_results": self.max_results,
            "is_ready": self.is_ready,
            "system_health": self.system_health,
            "error_statistics": self.error_handler.get_error_statistics() if self.error_handler else {}
        }
    
    async def update_knowledge_item(self, item_id: str, updates: Dict[str, Any]):
        """Update an existing knowledge item"""
        if item_id not in self.knowledge_items:
            raise ValueError(f"Knowledge item {item_id} not found")
        
        item = self.knowledge_items[item_id]
        
        # Update fields
        for field, value in updates.items():
            if hasattr(item, field):
                setattr(item, field, value)
        
        # Update timestamp
        item.last_updated = datetime.utcnow().isoformat()
        
        # Re-generate embedding if content changed
        if 'content' in updates and self.embedding_model:
            embedding = self.embedding_model.encode([item.content])[0]
            item.embedding = embedding.tolist()
        
        # Save to database
        await self.add_knowledge_item(item)  # This handles INSERT OR REPLACE
    
    async def delete_knowledge_item(self, item_id: str):
        """Delete a knowledge item"""
        if item_id not in self.knowledge_items:
            return
        
        try:
            # Remove from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM aviation_knowledge WHERE id = ?', (item_id,))
            conn.commit()
            conn.close()
            
            # Remove from memory
            del self.knowledge_items[item_id]
            
            # Update embeddings matrix
            await self._update_embeddings_matrix()
            
            logging.info(f"Deleted knowledge item: {item_id}")
            
        except Exception as e:
            logging.error(f"Error deleting knowledge item: {e}")
    
    async def _load_embedding_model_with_retry(self):
        """Load embedding model with retry logic"""
        for attempt in range(self.max_retries + 1):
            try:
                logging.info("Loading sentence transformer model...")
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                self.system_health["embedding_model_loaded"] = True
                return
            except Exception as e:
                if attempt == self.max_retries:
                    self.system_health["embedding_model_loaded"] = False
                    raise e
                logging.warning(f"Failed to load embedding model (attempt {attempt + 1}): {e}")
                await asyncio.sleep(self.retry_delay * (attempt + 1))
    
    async def _init_database_safe(self):
        """Initialize database with error handling"""
        try:
            await self._init_database()
            self.system_health["database_accessible"] = True
        except Exception as e:
            self.system_health["database_accessible"] = False
            await self.error_handler.handle_error(
                e,
                {"db_path": self.db_path},
                "rag_system",
                severity=ErrorSeverity.HIGH
            )
            raise
    
    async def _load_knowledge_base_safe(self):
        """Load knowledge base with error handling"""
        try:
            await self._load_knowledge_base()
            self.system_health["knowledge_items_loaded"] = len(self.knowledge_items) > 0
        except Exception as e:
            self.system_health["knowledge_items_loaded"] = False
            await self.error_handler.handle_error(
                e,
                {"data_dir": self.data_dir},
                "rag_system",
                severity=ErrorSeverity.MEDIUM
            )
            # Don't raise - we can continue with default data
    
    async def _load_default_aviation_data_safe(self):
        """Load default aviation data with error handling"""
        try:
            await self._load_default_aviation_data()
            self.system_health["knowledge_items_loaded"] = len(self.knowledge_items) > 0
        except Exception as e:
            self.system_health["knowledge_items_loaded"] = False
            await self.error_handler.handle_error(
                e,
                {"operation": "load_default_data"},
                "rag_system",
                severity=ErrorSeverity.HIGH
            )
            # Continue without default data
    
    async def _search_knowledge_with_retry(self, query: str, max_results: int = 5) -> List[Tuple[AviationKnowledge, float]]:
        """Search knowledge with retry logic"""
        for attempt in range(self.max_retries + 1):
            try:
                return await self._search_knowledge(query, max_results)
            except Exception as e:
                if attempt == self.max_retries:
                    logging.error(f"Knowledge search failed after {self.max_retries} retries: {e}")
                    return []
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        return []
    
    def _get_fallback_knowledge(self, query: str) -> str:
        """Provide fallback knowledge when search fails"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["weather", "metar", "taf"]):
            return """**Weather Information** (Source: Fallback Knowledge)
METAR reports provide current weather conditions at airports including wind, visibility, clouds, temperature, and pressure.
TAF reports provide terminal area forecasts with expected weather changes over time."""
        
        elif any(word in query_lower for word in ["aircraft", "plane", "cessna", "piper"]):
            return """**Aircraft Information** (Source: Fallback Knowledge)
General aviation aircraft include single-engine and multi-engine airplanes, helicopters, and gliders.
Key specifications include maximum speed, service ceiling, range, and engine type."""
        
        elif any(word in query_lower for word in ["regulation", "far", "rule"]):
            return """**Aviation Regulations** (Source: Fallback Knowledge)
Federal Aviation Regulations (FARs) govern aircraft operations, pilot requirements, and safety standards.
Key parts include Part 61 (pilot certification), Part 91 (general operating rules), and Part 135 (commercial operations)."""
        
        elif any(word in query_lower for word in ["flight", "planning", "navigation"]):
            return """**Flight Planning** (Source: Fallback Knowledge)
Flight planning involves route selection, weather analysis, fuel calculations, and performance planning.
Navigation methods include GPS, VOR, and pilotage using sectional charts."""
        
        else:
            return """**General Aviation Knowledge** (Source: Fallback Knowledge)
Aviation encompasses aircraft operations, weather, regulations, navigation, and flight planning.
Key areas include pilot training, aircraft systems, meteorology, and air traffic control."""
    
    async def _check_system_health(self):
        """Check system health and update status"""
        try:
            current_time = datetime.utcnow()
            
            # Check if we need to update health status
            if (current_time - self.system_health["last_health_check"]).total_seconds() < 300:
                return  # Skip if checked recently (5 minutes)
            
            # Check embedding model
            try:
                if self.embedding_model is not None:
                    # Test embedding generation
                    test_embedding = self.embedding_model.encode(["test"])
                    self.system_health["embedding_model_loaded"] = len(test_embedding) > 0
                else:
                    self.system_health["embedding_model_loaded"] = False
            except:
                self.system_health["embedding_model_loaded"] = False
            
            # Check database accessibility
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM aviation_knowledge')
                conn.close()
                self.system_health["database_accessible"] = True
            except:
                self.system_health["database_accessible"] = False
            
            # Check knowledge items
            self.system_health["knowledge_items_loaded"] = len(self.knowledge_items) > 0
            
            self.system_health["last_health_check"] = current_time
            
        except Exception as e:
            logging.error(f"Error checking RAG system health: {e}")