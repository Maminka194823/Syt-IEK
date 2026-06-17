"""
V4 Knowledge Base Management
Centralized aviation data storage with vector embeddings and hot updates
"""

import sqlite3
import json
import os
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor

@dataclass
class DataSource:
    """Data source configuration"""
    name: str
    type: str  # file, api, database
    location: str  # file path, URL, connection string
    priority: int  # Higher number = higher priority
    update_frequency: str  # daily, weekly, monthly, manual
    last_updated: Optional[str] = None
    is_active: bool = True

@dataclass
class KnowledgeItem:
    """Knowledge item with full metadata"""
    id: str
    title: str
    content: str
    source: str
    category: str
    subcategory: Optional[str]
    tags: List[str]
    priority: int
    last_updated: str
    content_hash: str
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None

class KnowledgeBase:
    """
    Centralized aviation knowledge base with vector embeddings
    Supports hot updates, data prioritization, and multiple data sources
    """
    
    def __init__(self, data_dir: str = "data/knowledge_base"):
        self.data_dir = data_dir
        self.db_path = os.path.join(data_dir, "knowledge_base.db")
        self.embeddings_path = os.path.join(data_dir, "embeddings.pkl")
        self.sources_path = os.path.join(data_dir, "data_sources.json")
        
        # Embedding model
        self.embedding_model = None
        self.embedding_dim = 384  # all-MiniLM-L6-v2 dimension
        
        # In-memory storage
        self.knowledge_items: Dict[str, KnowledgeItem] = {}
        self.data_sources: Dict[str, DataSource] = {}
        self.embeddings_matrix: Optional[np.ndarray] = None
        self.item_id_to_index: Dict[str, int] = {}
        
        # Threading for concurrent operations
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Configuration
        self.max_items = 10000
        self.embedding_batch_size = 32
        self.similarity_threshold = 0.3
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self):
        """Initialize the knowledge base"""
        self.logger.info("Initializing knowledge base...")
        
        try:
            # Load embedding model
            self.logger.info("Loading embedding model...")
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Initialize database
            await self._init_database()
            
            # Load data sources configuration
            await self._load_data_sources()
            
            # Load existing knowledge items
            await self._load_knowledge_items()
            
            # Load embeddings
            await self._load_embeddings()
            
            self.logger.info(f"Knowledge base initialized with {len(self.knowledge_items)} items")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize knowledge base: {e}")
            raise
    
    async def _init_database(self):
        """Initialize SQLite database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Knowledge items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT,
                tags TEXT,
                priority INTEGER DEFAULT 1,
                last_updated TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                metadata TEXT
            )
        ''')
        
        # Data sources table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_sources (
                name TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                location TEXT NOT NULL,
                priority INTEGER DEFAULT 1,
                update_frequency TEXT DEFAULT 'manual',
                last_updated TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON knowledge_items(category)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_source ON knowledge_items(source)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_priority ON knowledge_items(priority)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_updated ON knowledge_items(last_updated)')
        
        conn.commit()
        conn.close()
    
    async def _load_data_sources(self):
        """Load data sources configuration"""
        if os.path.exists(self.sources_path):
            try:
                with open(self.sources_path, 'r', encoding='utf-8') as f:
                    sources_data = json.load(f)
                
                for source_data in sources_data:
                    source = DataSource(**source_data)
                    self.data_sources[source.name] = source
                
                self.logger.info(f"Loaded {len(self.data_sources)} data sources")
                
            except Exception as e:
                self.logger.error(f"Error loading data sources: {e}")
        else:
            # Create default data sources
            await self._create_default_data_sources()
    
    async def _create_default_data_sources(self):
        """Create default data source configurations"""
        default_sources = [
            DataSource(
                name="FAA_Regulations",
                type="file",
                location="data/sources/faa_regulations.json",
                priority=10,
                update_frequency="monthly"
            ),
            DataSource(
                name="Aircraft_Database",
                type="file", 
                location="data/sources/aircraft_specs.json",
                priority=8,
                update_frequency="weekly"
            ),
            DataSource(
                name="Weather_Knowledge",
                type="file",
                location="data/sources/weather_info.json",
                priority=7,
                update_frequency="daily"
            ),
            DataSource(
                name="AIM_Procedures",
                type="file",
                location="data/sources/aim_procedures.json",
                priority=9,
                update_frequency="monthly"
            )
        ]
        
        for source in default_sources:
            self.data_sources[source.name] = source
        
        await self._save_data_sources()
    
    async def _save_data_sources(self):
        """Save data sources configuration"""
        try:
            sources_data = [asdict(source) for source in self.data_sources.values()]
            with open(self.sources_path, 'w', encoding='utf-8') as f:
                json.dump(sources_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving data sources: {e}")
    
    async def _load_knowledge_items(self):
        """Load knowledge items from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM knowledge_items ORDER BY priority DESC, last_updated DESC')
            rows = cursor.fetchall()
            
            for row in rows:
                item = KnowledgeItem(
                    id=row[0],
                    title=row[1],
                    content=row[2],
                    source=row[3],
                    category=row[4],
                    subcategory=row[5],
                    tags=json.loads(row[6]) if row[6] else [],
                    priority=row[7],
                    last_updated=row[8],
                    content_hash=row[9],
                    metadata=json.loads(row[10]) if row[10] else None
                )
                self.knowledge_items[item.id] = item
            
            conn.close()
            self.logger.info(f"Loaded {len(self.knowledge_items)} knowledge items from database")
            
        except Exception as e:
            self.logger.error(f"Error loading knowledge items: {e}")
    
    async def _load_embeddings(self):
        """Load embeddings from file"""
        if os.path.exists(self.embeddings_path):
            try:
                with open(self.embeddings_path, 'rb') as f:
                    embeddings_data = pickle.load(f)
                
                self.embeddings_matrix = embeddings_data['embeddings']
                item_ids = embeddings_data['item_ids']
                
                # Update item_id_to_index mapping
                self.item_id_to_index = {item_id: i for i, item_id in enumerate(item_ids)}
                
                # Assign embeddings to knowledge items
                for i, item_id in enumerate(item_ids):
                    if item_id in self.knowledge_items:
                        self.knowledge_items[item_id].embedding = self.embeddings_matrix[i].tolist()
                
                self.logger.info(f"Loaded embeddings for {len(item_ids)} items")
                
            except Exception as e:
                self.logger.error(f"Error loading embeddings: {e}")
                # Generate embeddings if loading fails
                await self._generate_all_embeddings()
        else:
            # Generate embeddings for all items
            await self._generate_all_embeddings()
    
    async def ingest_aviation_data(self, data_source: str, data: Dict[str, Any]):
        """
        Ingest aviation data from various sources
        Supports structured data ingestion with deduplication
        """
        try:
            with self.lock:
                source_info = self.data_sources.get(data_source)
                if not source_info:
                    raise ValueError(f"Unknown data source: {data_source}")
                
                items_added = 0
                items_updated = 0
                
                # Process data based on format
                if isinstance(data, dict) and 'items' in data:
                    items_data = data['items']
                elif isinstance(data, list):
                    items_data = data
                else:
                    raise ValueError("Data must be a list or dict with 'items' key")
                
                for item_data in items_data:
                    # Create knowledge item
                    item_id = item_data.get('id') or self._generate_item_id(item_data)
                    
                    # Calculate content hash for deduplication
                    content = item_data.get('content', '')
                    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                    
                    # Check if item exists and has changed
                    existing_item = self.knowledge_items.get(item_id)
                    if existing_item and existing_item.content_hash == content_hash:
                        continue  # No changes, skip
                    
                    # Create or update item
                    knowledge_item = KnowledgeItem(
                        id=item_id,
                        title=item_data.get('title', ''),
                        content=content,
                        source=data_source,
                        category=item_data.get('category', 'general'),
                        subcategory=item_data.get('subcategory'),
                        tags=item_data.get('tags', []),
                        priority=source_info.priority,
                        last_updated=datetime.utcnow().isoformat(),
                        content_hash=content_hash,
                        metadata=item_data.get('metadata')
                    )
                    
                    # Generate embedding
                    if self.embedding_model:
                        embedding = await self._generate_embedding(content)
                        knowledge_item.embedding = embedding.tolist()
                    
                    # Store item
                    if existing_item:
                        items_updated += 1
                    else:
                        items_added += 1
                    
                    self.knowledge_items[item_id] = knowledge_item
                    await self._save_knowledge_item(knowledge_item)
                
                # Update embeddings matrix
                await self._update_embeddings_matrix()
                
                # Update source timestamp
                source_info.last_updated = datetime.utcnow().isoformat()
                await self._save_data_sources()
                
                self.logger.info(f"Ingested data from {data_source}: {items_added} added, {items_updated} updated")
                
                return {
                    "items_added": items_added,
                    "items_updated": items_updated,
                    "total_items": len(self.knowledge_items)
                }
                
        except Exception as e:
            self.logger.error(f"Error ingesting data from {data_source}: {e}")
            raise
    
    def _generate_item_id(self, item_data: Dict[str, Any]) -> str:
        """Generate unique item ID from data"""
        title = item_data.get('title', '')
        content = item_data.get('content', '')
        source = item_data.get('source', '')
        
        # Create hash from key fields
        id_string = f"{title}_{content[:100]}_{source}"
        return hashlib.md5(id_string.encode('utf-8')).hexdigest()[:16]
    
    async def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text"""
        if not self.embedding_model:
            raise ValueError("Embedding model not loaded")
        
        # Run embedding generation in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            self.executor,
            lambda: self.embedding_model.encode([text])[0]
        )
        
        return embedding
    
    async def _generate_all_embeddings(self):
        """Generate embeddings for all knowledge items"""
        if not self.embedding_model:
            return
        
        self.logger.info("Generating embeddings for all knowledge items...")
        
        items_without_embeddings = [
            item for item in self.knowledge_items.values()
            if item.embedding is None
        ]
        
        if not items_without_embeddings:
            return
        
        # Process in batches
        for i in range(0, len(items_without_embeddings), self.embedding_batch_size):
            batch = items_without_embeddings[i:i + self.embedding_batch_size]
            texts = [item.content for item in batch]
            
            # Generate embeddings for batch
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                self.executor,
                lambda: self.embedding_model.encode(texts)
            )
            
            # Assign embeddings to items
            for item, embedding in zip(batch, embeddings):
                item.embedding = embedding.tolist()
            
            self.logger.info(f"Generated embeddings for batch {i//self.embedding_batch_size + 1}")
        
        # Update embeddings matrix
        await self._update_embeddings_matrix()
        
        self.logger.info("Finished generating all embeddings")
    
    async def _update_embeddings_matrix(self):
        """Update the embeddings matrix and save to file"""
        try:
            with self.lock:
                embeddings = []
                item_ids = []
                
                # Collect embeddings in priority order
                sorted_items = sorted(
                    self.knowledge_items.values(),
                    key=lambda x: (x.priority, x.last_updated),
                    reverse=True
                )
                
                for item in sorted_items:
                    if item.embedding:
                        embeddings.append(item.embedding)
                        item_ids.append(item.id)
                
                if embeddings:
                    self.embeddings_matrix = np.array(embeddings)
                    self.item_id_to_index = {item_id: i for i, item_id in enumerate(item_ids)}
                    
                    # Save to file
                    embeddings_data = {
                        'embeddings': self.embeddings_matrix,
                        'item_ids': item_ids,
                        'updated_at': datetime.utcnow().isoformat()
                    }
                    
                    with open(self.embeddings_path, 'wb') as f:
                        pickle.dump(embeddings_data, f)
                    
                    self.logger.info(f"Updated embeddings matrix with {len(embeddings)} items")
                
        except Exception as e:
            self.logger.error(f"Error updating embeddings matrix: {e}")
    
    async def _save_knowledge_item(self, item: KnowledgeItem):
        """Save knowledge item to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO knowledge_items 
                (id, title, content, source, category, subcategory, tags, priority, 
                 last_updated, content_hash, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item.id,
                item.title,
                item.content,
                item.source,
                item.category,
                item.subcategory,
                json.dumps(item.tags) if item.tags else None,
                item.priority,
                item.last_updated,
                item.content_hash,
                json.dumps(item.metadata) if item.metadata else None
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Error saving knowledge item {item.id}: {e}")
    
    async def vector_search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search
        Returns list of matching items with similarity scores
        """
        if self.embeddings_matrix is None or len(self.embeddings_matrix) == 0:
            return []
        
        try:
            query_vec = np.array(query_embedding)
            query_norm = np.linalg.norm(query_vec)
            
            # Handle zero vector case
            if query_norm == 0:
                return []
            
            # Calculate cosine similarities
            embeddings_norms = np.linalg.norm(self.embeddings_matrix, axis=1)
            
            # Avoid division by zero for embeddings
            valid_indices = embeddings_norms > 0
            if not np.any(valid_indices):
                return []
            
            similarities = np.zeros(len(self.embeddings_matrix))
            similarities[valid_indices] = np.dot(self.embeddings_matrix[valid_indices], query_vec) / (
                embeddings_norms[valid_indices] * query_norm
            )
            
            # Get top-k results above threshold
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                similarity = float(similarities[idx])
                if similarity >= self.similarity_threshold:
                    # Find item by index
                    item_id = None
                    for id_, index in self.item_id_to_index.items():
                        if index == idx:
                            item_id = id_
                            break
                    
                    if item_id and item_id in self.knowledge_items:
                        item = self.knowledge_items[item_id]
                        results.append({
                            "id": item.id,
                            "title": item.title,
                            "content": item.content,
                            "source": item.source,
                            "category": item.category,
                            "similarity": similarity,
                            "priority": item.priority,
                            "metadata": item.metadata
                        })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in vector search: {e}")
            return []
    
    async def get_real_time_data(self, data_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get real-time data (placeholder for external API integration)
        This would be implemented with specific aviation data APIs
        """
        # This is a placeholder - real implementation would integrate with:
        # - FAA APIs for NOTAMs, weather, etc.
        # - FlightAware for flight tracking
        # - Aviation weather services
        
        return {
            "data_type": data_type,
            "parameters": parameters,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {},
            "status": "not_implemented"
        }
    
    async def update_knowledge_item(self, item_id: str, updates: Dict[str, Any]):
        """Update an existing knowledge item"""
        if item_id not in self.knowledge_items:
            raise ValueError(f"Knowledge item {item_id} not found")
        
        with self.lock:
            item = self.knowledge_items[item_id]
            
            # Update fields
            for field, value in updates.items():
                if hasattr(item, field):
                    setattr(item, field, value)
            
            # Update timestamp and hash if content changed
            if 'content' in updates:
                item.content_hash = hashlib.md5(item.content.encode('utf-8')).hexdigest()
                
                # Re-generate embedding
                if self.embedding_model:
                    embedding = await self._generate_embedding(item.content)
                    item.embedding = embedding.tolist()
            
            item.last_updated = datetime.utcnow().isoformat()
            
            # Save to database
            await self._save_knowledge_item(item)
            
            # Update embeddings matrix if embedding changed
            if 'content' in updates:
                await self._update_embeddings_matrix()
    
    async def delete_knowledge_item(self, item_id: str):
        """Delete a knowledge item"""
        if item_id not in self.knowledge_items:
            return
        
        try:
            with self.lock:
                # Remove from database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM knowledge_items WHERE id = ?', (item_id,))
                conn.commit()
                conn.close()
                
                # Remove from memory
                del self.knowledge_items[item_id]
                
                # Update embeddings matrix
                await self._update_embeddings_matrix()
                
                self.logger.info(f"Deleted knowledge item: {item_id}")
                
        except Exception as e:
            self.logger.error(f"Error deleting knowledge item {item_id}: {e}")
    
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        category_counts = {}
        source_counts = {}
        
        for item in self.knowledge_items.values():
            category_counts[item.category] = category_counts.get(item.category, 0) + 1
            source_counts[item.source] = source_counts.get(item.source, 0) + 1
        
        return {
            "total_items": len(self.knowledge_items),
            "categories": category_counts,
            "sources": source_counts,
            "data_sources": len(self.data_sources),
            "embeddings_loaded": self.embeddings_matrix is not None,
            "embedding_dimension": self.embedding_dim,
            "similarity_threshold": self.similarity_threshold,
            "last_updated": max([item.last_updated for item in self.knowledge_items.values()]) if self.knowledge_items else None
        }
    
    async def cleanup_old_data(self, retention_days: int = 365):
        """Clean up old, low-priority data"""
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cutoff_str = cutoff_date.isoformat()
        
        items_to_remove = []
        
        with self.lock:
            for item_id, item in self.knowledge_items.items():
                # Remove old, low-priority items
                if (item.last_updated < cutoff_str and 
                    item.priority < 5 and 
                    item.category not in ['regulation', 'safety']):
                    items_to_remove.append(item_id)
            
            # Remove items
            for item_id in items_to_remove:
                await self.delete_knowledge_item(item_id)
            
            self.logger.info(f"Cleaned up {len(items_to_remove)} old knowledge items")
    
    async def shutdown(self):
        """Shutdown the knowledge base"""
        self.logger.info("Shutting down knowledge base...")
        
        # Save current state
        await self._save_data_sources()
        
        # Shutdown thread pool
        self.executor.shutdown(wait=True)
        
        self.logger.info("Knowledge base shutdown complete")