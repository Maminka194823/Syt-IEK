"""
Property-based tests for knowledge base data management
Feature: aviation-discord-bot, Property 10: Knowledge Base Data Management
"""

import pytest
import asyncio
import tempfile
import shutil
import os
import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings
from typing import Dict, List, Any
from datetime import datetime, timedelta

# Import the components we're testing
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from knowledge.knowledge_base import KnowledgeBase, KnowledgeItem, DataSource
import numpy as np


class MockSentenceTransformer:
    """Mock sentence transformer for testing"""
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model_name = model_name
    
    def encode(self, texts: List[str]) -> np.ndarray:
        # Generate consistent embeddings based on text content
        embeddings = []
        for text in texts:
            # Create deterministic embedding based on text hash
            text_hash = hash(text) % 1000000
            embedding = np.random.RandomState(text_hash).normal(0, 1, 384)  # 384-dim embedding
            embedding = embedding / np.linalg.norm(embedding)  # Normalize
            embeddings.append(embedding)
        return np.array(embeddings)


async def create_test_knowledge_base():
    """Create a test knowledge base with temporary directory"""
    temp_dir = tempfile.mkdtemp()
    
    with patch('knowledge.knowledge_base.SentenceTransformer', MockSentenceTransformer):
        kb = KnowledgeBase(data_dir=temp_dir)
        
        # Mock some methods to avoid file system operations during testing
        kb._save_data_sources = AsyncMock()
        
        await kb.initialize()
        return kb, temp_dir


def cleanup_test_knowledge_base(temp_dir: str):
    """Clean up test knowledge base directory"""
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


# Property-based test strategies
@st.composite
def aviation_data_strategy(draw):
    """Generate realistic aviation data for ingestion testing"""
    categories = ["regulation", "aircraft", "weather", "procedure", "airport", "navigation"]
    sources = ["FAA_Regulations", "Aircraft_Database", "Weather_Knowledge", "AIM_Procedures"]
    
    num_items = draw(st.integers(min_value=1, max_value=10))
    items = []
    
    for i in range(num_items):
        item = {
            "id": f"test_item_{i}_{draw(st.integers(min_value=1000, max_value=9999))}",
            "title": draw(st.text(min_size=10, max_size=100)),
            "content": draw(st.text(min_size=50, max_size=1000)),
            "category": draw(st.sampled_from(categories)),
            "subcategory": draw(st.one_of(st.none(), st.text(min_size=5, max_size=50))),
            "tags": draw(st.lists(st.text(min_size=3, max_size=20), min_size=0, max_size=5)),
            "metadata": {
                "priority": draw(st.integers(min_value=1, max_value=10)),
                "author": draw(st.text(min_size=5, max_size=30)),
                "version": draw(st.text(min_size=3, max_size=10))
            }
        }
        items.append(item)
    
    return {
        "source": draw(st.sampled_from(sources)),
        "items": items
    }


@st.composite
def data_source_strategy(draw):
    """Generate data source configurations"""
    source_types = ["file", "api", "database"]
    frequencies = ["daily", "weekly", "monthly", "manual"]
    
    return DataSource(
        name=draw(st.text(min_size=5, max_size=30)),
        type=draw(st.sampled_from(source_types)),
        location=draw(st.text(min_size=10, max_size=100)),
        priority=draw(st.integers(min_value=1, max_value=10)),
        update_frequency=draw(st.sampled_from(frequencies)),
        is_active=draw(st.booleans())
    )


@st.composite
def knowledge_item_strategy(draw):
    """Generate knowledge items for testing"""
    categories = ["regulation", "aircraft", "weather", "procedure", "airport"]
    
    # Generate truly unique ID using timestamp and random number
    import time
    unique_id = f"test_item_{int(time.time() * 1000000)}_{draw(st.integers(min_value=1000, max_value=9999))}"
    
    return KnowledgeItem(
        id=unique_id,
        title=draw(st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs')))),
        content=draw(st.text(min_size=50, max_size=2000, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Pc')))),
        source=draw(st.text(min_size=5, max_size=30, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))),
        category=draw(st.sampled_from(categories)),
        subcategory=draw(st.one_of(st.none(), st.text(min_size=5, max_size=30, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))),
        tags=draw(st.lists(st.text(min_size=3, max_size=15, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))), min_size=0, max_size=5)),
        priority=draw(st.integers(min_value=1, max_value=10)),
        last_updated=datetime.utcnow().isoformat(),
        content_hash=draw(st.text(min_size=16, max_size=32, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    )


class TestKnowledgeBaseDataManagement:
    """
    Property 10: Knowledge Base Data Management
    For any aviation data ingestion, update, or retrieval operation, the knowledge base
    should handle multiple data formats, prioritize official sources, maintain data
    provenance, use vector similarity search, and support hot updates without downtime.
    """
    
    @given(aviation_data_strategy())
    @settings(max_examples=50, deadline=30000)
    @pytest.mark.asyncio
    async def test_data_ingestion_consistency(self, aviation_data):
        """
        Property test: Data ingestion should handle multiple formats consistently
        Validates: Requirements 8.1, 8.2, 8.3
        """
        kb, temp_dir = await create_test_knowledge_base()
        
        try:
            # Property: Data ingestion should handle structured data
            result = await kb.ingest_aviation_data(aviation_data["source"], aviation_data)
            
            # Property: Ingestion should return valid statistics
            assert isinstance(result, dict), "Ingestion should return statistics dictionary"
            assert "items_added" in result, "Result should include items_added count"
            assert "items_updated" in result, "Result should include items_updated count"
            assert "total_items" in result, "Result should include total_items count"
            
            # Property: Items should be stored in knowledge base
            assert len(kb.knowledge_items) >= len(aviation_data["items"]), \
                "Knowledge base should contain ingested items"
            
            # Property: Each ingested item should have required fields
            for item_data in aviation_data["items"]:
                item_id = item_data.get("id")
                if item_id and item_id in kb.knowledge_items:
                    stored_item = kb.knowledge_items[item_id]
                    
                    assert stored_item.title == item_data["title"], "Title should be preserved"
                    assert stored_item.content == item_data["content"], "Content should be preserved"
                    assert stored_item.category == item_data["category"], "Category should be preserved"
                    assert stored_item.source == aviation_data["source"], "Source should be set correctly"
                    
                    # Property: Items should have embeddings generated
                    assert stored_item.embedding is not None, "Items should have embeddings"
                    assert len(stored_item.embedding) == 384, "Embeddings should have correct dimension"
            
            # Property: Data source should be updated
            source_name = aviation_data["source"]
            if source_name in kb.data_sources:
                source = kb.data_sources[source_name]
                assert source.last_updated is not None, "Data source should have updated timestamp"
            
        finally:
            cleanup_test_knowledge_base(temp_dir)
    
    @given(st.lists(aviation_data_strategy(), min_size=2, max_size=5))
    @settings(max_examples=30, deadline=45000)
    @pytest.mark.asyncio
    async def test_data_prioritization(self, multiple_data_sources):
        """
        Property test: Data should be prioritized by official sources
        Validates: Requirements 8.4
        """
        kb, temp_dir = await create_test_knowledge_base()
        
        try:
            # Ingest data from multiple sources with different priorities
            for data in multiple_data_sources:
                await kb.ingest_aviation_data(data["source"], data)
            
            # Property: Items should be ordered by priority
            sorted_items = sorted(kb.knowledge_items.values(), key=lambda x: x.priority, reverse=True)
            
            # Verify priority ordering
            for i in range(len(sorted_items) - 1):
                assert sorted_items[i].priority >= sorted_items[i + 1].priority, \
                    "Items should be ordered by priority (highest first)"
            
            # Property: Higher priority sources should be preferred in search results
            if len(kb.knowledge_items) > 1:
                # Create a query embedding
                query_text = "aviation test query"
                query_embedding = kb.embedding_model.encode([query_text])[0].tolist()
                
                # Perform vector search
                results = await kb.vector_search(query_embedding, top_k=5)
                
                # Property: Results should consider priority in ranking
                if len(results) > 1:
                    # Among results with similar similarity, higher priority should come first
                    for i in range(len(results) - 1):
                        curr_sim = results[i]["similarity"]
                        next_sim = results[i + 1]["similarity"]
                        curr_priority = results[i]["priority"]
                        next_priority = results[i + 1]["priority"]
                        
                        # If similarities are very close, priority should determine order
                        if abs(curr_sim - next_sim) < 0.1:
                            assert curr_priority >= next_priority, \
                                "Higher priority items should rank higher when similarities are close"
        
        finally:
            cleanup_test_knowledge_base(temp_dir)
    
    @given(knowledge_item_strategy())
    @settings(max_examples=50, deadline=20000)
    @pytest.mark.asyncio
    async def test_data_provenance_maintenance(self, knowledge_item):
        """
        Property test: Data provenance should be maintained
        Validates: Requirements 8.6
        """
        kb, temp_dir = await create_test_knowledge_base()
        
        try:
            # Add knowledge item
            kb.knowledge_items[knowledge_item.id] = knowledge_item
            await kb._save_knowledge_item(knowledge_item)
            
            # Property: Item should maintain source information
            stored_item = kb.knowledge_items[knowledge_item.id]
            assert stored_item.source == knowledge_item.source, "Source should be preserved"
            assert stored_item.last_updated is not None, "Last updated should be set"
            assert stored_item.content_hash is not None, "Content hash should be maintained"
            
            # Property: Metadata should be preserved
            if knowledge_item.metadata:
                assert stored_item.metadata == knowledge_item.metadata, "Metadata should be preserved"
            
            # Property: Tags should be preserved
            assert stored_item.tags == knowledge_item.tags, "Tags should be preserved"
            
            # Property: Category and subcategory should be preserved
            assert stored_item.category == knowledge_item.category, "Category should be preserved"
            assert stored_item.subcategory == knowledge_item.subcategory, "Subcategory should be preserved"
            
        finally:
            cleanup_test_knowledge_base(temp_dir)
    
    @given(st.lists(st.floats(min_value=-1.0, max_value=1.0), min_size=384, max_size=384))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_vector_similarity_search(self, query_embedding):
        """
        Property test: Vector similarity search should work correctly
        Validates: Requirements 8.3
        """
        kb, temp_dir = await create_test_knowledge_base()
        
        try:
            # Add some test items with embeddings
            test_items = [
                KnowledgeItem(
                    id=f"test_{i}",
                    title=f"Test Item {i}",
                    content=f"Test content for item {i}",
                    source="test_source",
                    category="test",
                    subcategory=None,
                    tags=[],
                    priority=5,
                    last_updated=datetime.utcnow().isoformat(),
                    content_hash=f"hash_{i}",
                    embedding=kb.embedding_model.encode([f"Test content for item {i}"])[0].tolist()
                )
                for i in range(5)
            ]
            
            for item in test_items:
                kb.knowledge_items[item.id] = item
            
            # Update embeddings matrix
            await kb._update_embeddings_matrix()
            
            # Perform vector search
            results = await kb.vector_search(query_embedding, top_k=3)
            
            # Property: Results should be a list
            assert isinstance(results, list), "Search results should be a list"
            
            # Property: Results should not exceed top_k
            assert len(results) <= 3, "Results should not exceed top_k parameter"
            
            # Property: Each result should have required fields
            for result in results:
                assert isinstance(result, dict), "Each result should be a dictionary"
                assert "id" in result, "Result should have id"
                assert "title" in result, "Result should have title"
                assert "content" in result, "Result should have content"
                assert "source" in result, "Result should have source"
                assert "category" in result, "Result should have category"
                assert "similarity" in result, "Result should have similarity score"
                assert "priority" in result, "Result should have priority"
                
                # Property: Similarity should be valid
                assert isinstance(result["similarity"], (int, float)), "Similarity should be numeric"
                assert -1.0 <= result["similarity"] <= 1.0, "Similarity should be between -1 and 1"
                
                # Property: Similarity should meet threshold
                assert result["similarity"] >= kb.similarity_threshold, \
                    f"Similarity {result['similarity']} should meet threshold {kb.similarity_threshold}"
            
            # Property: Results should be ordered by similarity
            if len(results) > 1:
                similarities = [r["similarity"] for r in results]
                assert similarities == sorted(similarities, reverse=True), \
                    "Results should be ordered by similarity (highest first)"
        
        finally:
            cleanup_test_knowledge_base(temp_dir)
    
    @given(aviation_data_strategy())
    @settings(max_examples=30, deadline=30000)
    @pytest.mark.asyncio
    async def test_hot_updates_without_downtime(self, aviation_data):
        """
        Property test: Hot updates should work without downtime
        Validates: Requirements 8.2
        """
        kb, temp_dir = await create_test_knowledge_base()
        
        try:
            # Initial data ingestion
            await kb.ingest_aviation_data(aviation_data["source"], aviation_data)
            initial_count = len(kb.knowledge_items)
            
            # Property: Knowledge base should remain accessible during updates
            assert len(kb.knowledge_items) > 0, "Knowledge base should have items after initial ingestion"
            
            # Simulate concurrent access during update
            async def concurrent_search():
                query_embedding = kb.embedding_model.encode(["test query"])[0].tolist()
                results = await kb.vector_search(query_embedding, top_k=5)
                return len(results)
            
            # Start concurrent search
            search_task = asyncio.create_task(concurrent_search())
            
            # Perform hot update (modify existing data)
            updated_data = aviation_data.copy()
            for item in updated_data["items"]:
                item["content"] = item["content"] + " UPDATED"
            
            # Ingest updated data
            update_result = await kb.ingest_aviation_data(aviation_data["source"], updated_data)
            
            # Wait for concurrent search to complete
            search_results_count = await search_task
            
            # Property: Concurrent operations should complete successfully
            assert isinstance(search_results_count, int), "Concurrent search should complete"
            assert search_results_count >= 0, "Search should return valid result count"
            
            # Property: Updates should be reflected in knowledge base
            assert isinstance(update_result, dict), "Update should return statistics"
            assert "items_updated" in update_result, "Update result should show updated items"
            
            # Property: Knowledge base should maintain consistency
            assert len(kb.knowledge_items) >= initial_count, "Item count should be maintained or increased"
            
            # Property: Updated content should be reflected
            for item_data in updated_data["items"]:
                item_id = item_data.get("id")
                if item_id and item_id in kb.knowledge_items:
                    stored_item = kb.knowledge_items[item_id]
                    assert "UPDATED" in stored_item.content, "Updated content should be reflected"
        
        finally:
            cleanup_test_knowledge_base(temp_dir)
    
    @given(st.lists(knowledge_item_strategy(), min_size=5, max_size=20))
    @settings(max_examples=20, deadline=30000)
    @pytest.mark.asyncio
    async def test_embeddings_matrix_consistency(self, knowledge_items):
        """
        Property test: Embeddings matrix should remain consistent
        Validates: Requirements 8.3
        """
        kb, temp_dir = await create_test_knowledge_base()
        
        try:
            # Ensure unique IDs by modifying duplicates
            unique_items = []
            seen_ids = set()
            
            for i, item in enumerate(knowledge_items):
                if item.id in seen_ids:
                    # Make ID unique by appending index
                    item.id = f"{item.id}_{i}"
                seen_ids.add(item.id)
                unique_items.append(item)
            
            # Add knowledge items with unique IDs
            for item in unique_items:
                # Generate embedding for item
                embedding = kb.embedding_model.encode([item.content])[0]
                item.embedding = embedding.tolist()
                kb.knowledge_items[item.id] = item
            
            # Update embeddings matrix
            await kb._update_embeddings_matrix()
            
            # Property: Embeddings matrix should exist
            assert kb.embeddings_matrix is not None, "Embeddings matrix should be created"
            
            # Property: Matrix dimensions should be correct
            expected_rows = len(unique_items)  # All items should have embeddings
            assert kb.embeddings_matrix.shape[0] == expected_rows, \
                f"Matrix should have {expected_rows} rows, got {kb.embeddings_matrix.shape[0]}"
            assert kb.embeddings_matrix.shape[1] == 384, "Matrix should have 384 columns"
            
            # Property: Item ID to index mapping should be consistent
            assert len(kb.item_id_to_index) == expected_rows, \
                "Item ID mapping should match matrix rows"
            
            # Property: All embeddings should be normalized
            for i in range(kb.embeddings_matrix.shape[0]):
                embedding_norm = np.linalg.norm(kb.embeddings_matrix[i])
                assert 0.9 <= embedding_norm <= 1.1, \
                    f"Embedding {i} should be approximately normalized, got norm {embedding_norm}"
            
            # Property: Matrix should be consistent with individual item embeddings
            for item_id, index in kb.item_id_to_index.items():
                if item_id in kb.knowledge_items:
                    item = kb.knowledge_items[item_id]
                    if item.embedding:
                        matrix_embedding = kb.embeddings_matrix[index]
                        item_embedding = np.array(item.embedding)
                        
                        # Should be very similar (allowing for floating point precision)
                        similarity = np.dot(matrix_embedding, item_embedding)
                        assert similarity > 0.99, \
                            f"Matrix embedding should match item embedding for {item_id}"
        
        finally:
            cleanup_test_knowledge_base(temp_dir)
    
    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=20, deadline=500)
    @pytest.mark.asyncio
    async def test_data_cleanup_and_retention(self, retention_days):
        """
        Property test: Data cleanup should respect retention policies
        Validates: Requirements 8.5
        """
        kb, temp_dir = await create_test_knowledge_base()
        
        try:
            # Create items with different ages and priorities
            old_date = (datetime.utcnow() - timedelta(days=retention_days + 10)).isoformat()
            recent_date = (datetime.utcnow() - timedelta(days=retention_days - 10)).isoformat()
            
            old_low_priority = KnowledgeItem(
                id="old_low",
                title="Old Low Priority",
                content="Old content",
                source="test",
                category="general",  # Not protected category
                subcategory=None,
                tags=[],
                priority=3,  # Low priority
                last_updated=old_date,
                content_hash="hash1"
            )
            
            old_high_priority = KnowledgeItem(
                id="old_high",
                title="Old High Priority",
                content="Old important content",
                source="test",
                category="regulation",  # Protected category
                subcategory=None,
                tags=[],
                priority=8,  # High priority
                last_updated=old_date,
                content_hash="hash2"
            )
            
            recent_item = KnowledgeItem(
                id="recent",
                title="Recent Item",
                content="Recent content",
                source="test",
                category="general",
                subcategory=None,
                tags=[],
                priority=3,
                last_updated=recent_date,
                content_hash="hash3"
            )
            
            # Add items to knowledge base
            for item in [old_low_priority, old_high_priority, recent_item]:
                kb.knowledge_items[item.id] = item
                await kb._save_knowledge_item(item)
            
            initial_count = len(kb.knowledge_items)
            
            # Perform cleanup
            await kb.cleanup_old_data(retention_days)
            
            # Property: Recent items should be preserved
            assert "recent" in kb.knowledge_items, "Recent items should be preserved"
            
            # Property: High priority or protected category items should be preserved
            assert "old_high" in kb.knowledge_items, \
                "High priority or protected category items should be preserved"
            
            # Property: Old low priority items may be removed
            # (This is implementation dependent, but we can check consistency)
            final_count = len(kb.knowledge_items)
            assert final_count <= initial_count, "Cleanup should not increase item count"
            
            # Property: Remaining items should meet retention criteria
            for item in kb.knowledge_items.values():
                item_date = datetime.fromisoformat(item.last_updated)
                cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
                
                # If item is old, it should have high priority or protected category
                if item_date < cutoff_date:
                    assert (item.priority >= 5 or 
                           item.category in ['regulation', 'safety']), \
                        f"Old item {item.id} should have high priority or protected category"
        
        finally:
            cleanup_test_knowledge_base(temp_dir)
    
    @given(data_source_strategy())
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_data_source_management(self, data_source):
        """
        Property test: Data sources should be properly managed
        Validates: Requirements 8.1, 8.2
        """
        kb, temp_dir = await create_test_knowledge_base()
        
        try:
            # Add data source
            kb.data_sources[data_source.name] = data_source
            
            # Property: Data source should be stored
            assert data_source.name in kb.data_sources, "Data source should be stored"
            stored_source = kb.data_sources[data_source.name]
            
            # Property: All fields should be preserved
            assert stored_source.name == data_source.name, "Name should be preserved"
            assert stored_source.type == data_source.type, "Type should be preserved"
            assert stored_source.location == data_source.location, "Location should be preserved"
            assert stored_source.priority == data_source.priority, "Priority should be preserved"
            assert stored_source.update_frequency == data_source.update_frequency, \
                "Update frequency should be preserved"
            assert stored_source.is_active == data_source.is_active, "Active status should be preserved"
            
            # Property: Data source should support updates
            original_priority = data_source.priority
            stored_source.priority = original_priority + 1
            
            assert kb.data_sources[data_source.name].priority == original_priority + 1, \
                "Data source updates should be reflected"
            
        finally:
            cleanup_test_knowledge_base(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])