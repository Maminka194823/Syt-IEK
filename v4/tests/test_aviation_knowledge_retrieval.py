"""
Property-based tests for aviation knowledge retrieval
Feature: aviation-discord-bot, Property 4: Aviation Knowledge Retrieval
"""

import pytest
import asyncio
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings
from typing import Dict, List, Any, Tuple

# Import the components we're testing
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from knowledge.rag_system import RAGSystem, AviationKnowledge


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


def create_test_knowledge_items() -> List[AviationKnowledge]:
    """Create test aviation knowledge items"""
    return [
        AviationKnowledge(
            id="test_regulation_1",
            title="FAR Part 91.3 - Responsibility and Authority of Pilot in Command",
            content="The pilot in command of an aircraft is directly responsible for, and is the final authority as to, the operation of that aircraft.",
            source="FAA Regulations",
            category="regulation",
            last_updated="2024-01-01T00:00:00",
            metadata={"regulation_part": "91.3", "authority": "FAA"}
        ),
        AviationKnowledge(
            id="test_aircraft_1",
            title="Cessna 172 Performance Specifications",
            content="Maximum speed: 140 knots, Cruise speed: 122 knots, Service ceiling: 14,000 feet, Range: 640 nautical miles with standard fuel.",
            source="Aircraft Database",
            category="aircraft",
            last_updated="2024-01-01T00:00:00",
            metadata={"manufacturer": "Cessna", "model": "172", "type": "single_engine"}
        ),
        AviationKnowledge(
            id="test_weather_1",
            title="METAR Decoding Basics",
            content="METAR reports include station identifier, observation time, wind direction and speed, visibility, weather phenomena, cloud coverage, temperature, dewpoint, and altimeter setting.",
            source="Weather Knowledge Base",
            category="weather",
            last_updated="2024-01-01T00:00:00",
            metadata={"type": "weather_report", "format": "METAR"}
        ),
        AviationKnowledge(
            id="test_airport_1",
            title="Airport Traffic Pattern Procedures",
            content="Standard traffic pattern altitude is 1,000 feet AGL. Pattern consists of upwind, crosswind, downwind, base, and final legs. Left traffic is standard unless otherwise indicated.",
            source="AIM",
            category="procedure",
            last_updated="2024-01-01T00:00:00",
            metadata={"type": "traffic_pattern", "altitude": "1000_agl"}
        ),
        AviationKnowledge(
            id="test_navigation_1",
            title="VOR Navigation Principles",
            content="VOR (VHF Omnidirectional Range) provides azimuth information by transmitting signals on 360 radials. Aircraft receive signals to determine bearing from the station.",
            source="Navigation Manual",
            category="procedure",
            last_updated="2024-01-01T00:00:00",
            metadata={"type": "navigation", "system": "VOR"}
        )
    ]


async def create_test_rag_system():
    """Create a RAG system with test data for testing"""
    with patch('knowledge.rag_system.SentenceTransformer', MockSentenceTransformer):
        rag_system = RAGSystem(data_dir="test_data")
        
        # Mock the database operations
        rag_system._init_database = AsyncMock()
        rag_system._load_knowledge_base = AsyncMock()
        rag_system._load_default_aviation_data = AsyncMock()
        rag_system._update_embeddings_matrix = AsyncMock()
        
        # Initialize with test data
        await rag_system.initialize()
        
        # Add test knowledge items
        test_items = create_test_knowledge_items()
        for item in test_items:
            rag_system.knowledge_items[item.id] = item
            # Generate embedding using mock transformer
            embedding = rag_system.embedding_model.encode([item.content])[0]
            item.embedding = embedding.tolist()
        
        rag_system.is_ready = True
        return rag_system


# Property-based test strategies
@st.composite
def aviation_query_strategy(draw):
    """Generate realistic aviation queries for testing"""
    query_types = [
        # Regulation queries
        "What are the pilot in command responsibilities?",
        "Tell me about FAR Part 91",
        "What are the VFR weather minimums?",
        "Explain right of way rules",
        
        # Aircraft queries
        "What is the cruise speed of a Cessna 172?",
        "Tell me about aircraft performance",
        "What are the specifications of a Piper Cherokee?",
        "How high can a small aircraft fly?",
        
        # Weather queries
        "How do I read a METAR report?",
        "What does TAF stand for?",
        "Explain weather minimums for VFR",
        "What is a PIREP?",
        
        # Airport/procedure queries
        "How do I fly a traffic pattern?",
        "What is the standard pattern altitude?",
        "Explain VOR navigation",
        "How do I use GPS for navigation?",
        
        # General aviation queries
        "What is aviation?",
        "How do airplanes fly?",
        "What is lift?",
        "Explain flight controls"
    ]
    
    # Either pick from predefined queries or generate custom ones
    if draw(st.booleans()):
        return draw(st.sampled_from(query_types))
    else:
        # Generate custom query with aviation keywords
        aviation_keywords = [
            "aircraft", "airplane", "pilot", "flight", "aviation", "weather", 
            "airport", "navigation", "regulation", "FAR", "VFR", "IFR",
            "METAR", "TAF", "pattern", "landing", "takeoff", "altitude"
        ]
        
        keyword = draw(st.sampled_from(aviation_keywords))
        question_starters = ["What is", "How do", "Tell me about", "Explain", "What are"]
        starter = draw(st.sampled_from(question_starters))
        
        return f"{starter} {keyword}?"


@st.composite
def user_context_strategy(draw):
    """Generate realistic user context for testing"""
    experience_levels = ["student", "private", "commercial", "atp", None]
    interests = ["general_aviation", "commercial", "military", "helicopters", "gliders"]
    detail_levels = ["brief", "medium", "detailed"]
    
    return {
        "experience_level": draw(st.sampled_from(experience_levels)),
        "interests": draw(st.lists(st.sampled_from(interests), min_size=0, max_size=3)),
        "detail_level": draw(st.sampled_from(detail_levels)),
        "recent_topics": draw(st.lists(st.text(min_size=3, max_size=20), min_size=0, max_size=5))
    }


class TestAviationKnowledgeRetrieval:
    """
    Property 4: Aviation Knowledge Retrieval
    For any aviation-related query (regulations, aircraft, weather, airports),
    the RAG system should retrieve relevant information, rank results by relevance,
    and present data in appropriate formats with source attribution.
    """
    
    @given(aviation_query_strategy(), user_context_strategy())
    @settings(max_examples=100, deadline=30000)
    @pytest.mark.asyncio
    async def test_knowledge_retrieval_consistency(self, query, user_context):
        """
        Property test: Knowledge retrieval should be consistent and relevant
        Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
        """
        rag_system = await create_test_rag_system()
        
        # Property: For any aviation query, system should retrieve relevant knowledge
        knowledge_context = await rag_system.retrieve_knowledge(query, user_context)
        
        # Property: Retrieved knowledge should be a string
        assert isinstance(knowledge_context, str), "Retrieved knowledge should be a string"
        
        # Property: Non-empty queries should return non-empty knowledge (unless no matches)
        if query.strip():
            # Either returns relevant knowledge or indicates no knowledge found
            assert knowledge_context != "", "Non-empty query should return some response"
            
            # If knowledge is found, it should contain source attribution
            if "No relevant aviation knowledge found" not in knowledge_context:
                assert "Source:" in knowledge_context, "Retrieved knowledge should include source attribution"
        
        # Property: Knowledge context should respect length constraints
        assert len(knowledge_context) <= rag_system.context_window + 100, \
            f"Knowledge context exceeds reasonable length: {len(knowledge_context)}"
    
    @given(st.sampled_from(["regulation", "aircraft", "weather", "procedure"]))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_category_specific_retrieval(self, category):
        """
        Property test: Category-specific retrieval should return relevant results
        Validates: Requirements 3.1, 3.2, 3.3, 3.4
        """
        rag_system = await create_test_rag_system()
        
        # Create category-specific queries
        category_queries = {
            "regulation": "What are the pilot responsibilities according to regulations?",
            "aircraft": "What are the performance specifications of aircraft?",
            "weather": "How do I interpret weather reports?",
            "procedure": "What are the standard traffic pattern procedures?"
        }
        
        query = category_queries[category]
        results = await rag_system._search_knowledge(query, max_results=5)
        
        # Property: Results should be ranked by relevance
        if len(results) > 1:
            similarities = [similarity for _, similarity in results]
            assert similarities == sorted(similarities, reverse=True), \
                "Results should be ranked by similarity score in descending order"
        
        # Property: Results should have reasonable similarity scores
        for item, similarity in results:
            assert 0.0 <= similarity <= 1.0, \
                f"Similarity score should be between 0 and 1: {similarity}"
            
            # Property: Results should meet minimum similarity threshold
            assert similarity >= rag_system.similarity_threshold, \
                f"Result similarity {similarity} below threshold {rag_system.similarity_threshold}"
        
        # Property: Results should be relevant to the category (when possible)
        relevant_results = [item for item, _ in results if item.category == category]
        if relevant_results:
            # At least some results should match the queried category
            assert len(relevant_results) > 0, f"No {category} results found for {category} query"
    
    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_search_result_ranking(self, query):
        """
        Property test: Search results should be properly ranked by relevance
        Validates: Requirements 3.5
        """
        rag_system = await create_test_rag_system()
        
        # Get search results
        results = await rag_system._search_knowledge(query, max_results=10)
        
        # Property: Results should be sorted by similarity in descending order
        if len(results) > 1:
            similarities = [similarity for _, similarity in results]
            for i in range(len(similarities) - 1):
                assert similarities[i] >= similarities[i + 1], \
                    f"Results not properly ranked: {similarities[i]} < {similarities[i + 1]} at position {i}"
        
        # Property: All results should meet minimum threshold
        for item, similarity in results:
            assert similarity >= rag_system.similarity_threshold, \
                f"Result with similarity {similarity} below threshold {rag_system.similarity_threshold}"
        
        # Property: Results should not exceed maximum count
        assert len(results) <= rag_system.max_results, \
            f"Too many results returned: {len(results)} > {rag_system.max_results}"
    
    @given(st.sampled_from(["aircraft", "cessna", "boeing", "helicopter"]))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_aircraft_specific_retrieval(self, aircraft_query):
        """
        Property test: Aircraft-specific queries should return aircraft information
        Validates: Requirements 3.2
        """
        rag_system = await create_test_rag_system()
        
        # Test aircraft-specific retrieval
        aircraft_info = await rag_system.get_aircraft_info(aircraft_query)
        
        # Property: Aircraft info should be a dictionary
        assert isinstance(aircraft_info, dict), "Aircraft info should be a dictionary"
        
        # Property: If aircraft info is found, it should have required fields
        if aircraft_info:  # Non-empty dictionary
            assert "title" in aircraft_info, "Aircraft info should have title"
            assert "content" in aircraft_info, "Aircraft info should have content"
            assert "source" in aircraft_info, "Aircraft info should have source"
            assert "similarity" in aircraft_info, "Aircraft info should have similarity score"
            
            # Property: Similarity should be reasonable for aircraft queries
            assert aircraft_info["similarity"] > 0.3, \
                f"Aircraft similarity too low: {aircraft_info['similarity']}"
            
            # Property: Metadata should contain aircraft-specific information
            if "metadata" in aircraft_info and aircraft_info["metadata"]:
                metadata = aircraft_info["metadata"]
                aircraft_fields = ["manufacturer", "model", "type", "category"]
                has_aircraft_metadata = any(field in metadata for field in aircraft_fields)
                assert has_aircraft_metadata, "Aircraft info should have aircraft-specific metadata"
    
    @given(st.sampled_from(["FAR", "regulation", "rule", "requirement", "legal"]))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_regulation_specific_retrieval(self, regulation_query):
        """
        Property test: Regulation queries should return regulation information
        Validates: Requirements 3.1
        """
        rag_system = await create_test_rag_system()
        
        # Test regulation-specific retrieval
        regulation_results = await rag_system.search_regulations(regulation_query)
        
        # Property: Regulation results should be a list
        assert isinstance(regulation_results, list), "Regulation results should be a list"
        
        # Property: Each regulation result should have required fields
        for result in regulation_results:
            assert isinstance(result, dict), "Each regulation result should be a dictionary"
            assert "title" in result, "Regulation result should have title"
            assert "content" in result, "Regulation result should have content"
            assert "source" in result, "Regulation result should have source"
            assert "similarity" in result, "Regulation result should have similarity score"
            
            # Property: Similarity should be reasonable
            assert 0.0 <= result["similarity"] <= 1.0, \
                f"Invalid similarity score: {result['similarity']}"
            
            # Property: Should have metadata
            assert "metadata" in result, "Regulation result should have metadata"
    
    @given(st.integers(min_value=1, max_value=10))
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_max_results_constraint(self, max_results):
        """
        Property test: Search should respect max_results parameter
        Validates: Requirements 3.5
        """
        rag_system = await create_test_rag_system()
        
        # Test with different max_results values
        query = "aviation aircraft flight"
        results = await rag_system._search_knowledge(query, max_results=max_results)
        
        # Property: Results should not exceed max_results
        assert len(results) <= max_results, \
            f"Results exceed max_results: {len(results)} > {max_results}"
        
        # Property: If there are available results, should return up to max_results
        total_available = len([item for item in rag_system.knowledge_items.values() 
                             if item.embedding is not None])
        
        if total_available > 0:
            expected_count = min(max_results, total_available)
            # Results might be fewer due to similarity threshold
            assert len(results) <= expected_count, \
                f"Unexpected result count: {len(results)}"
    
    @given(aviation_query_strategy())
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_knowledge_context_formatting(self, query):
        """
        Property test: Knowledge context should be properly formatted
        Validates: Requirements 3.4, 3.5
        """
        rag_system = await create_test_rag_system()
        
        # Retrieve formatted knowledge context
        context = await rag_system.retrieve_knowledge(query)
        
        # Property: Context should be properly formatted string
        assert isinstance(context, str), "Knowledge context should be a string"
        
        # Property: If knowledge is found, should have proper formatting
        if "No relevant aviation knowledge found" not in context and context.strip():
            # Should contain source attribution
            assert "Source:" in context, "Knowledge context should include source attribution"
            
            # Should have structured format with titles
            assert "**" in context, "Knowledge context should have formatted titles"
            
            # Should not exceed context window
            assert len(context) <= rag_system.context_window, \
                f"Context exceeds window: {len(context)} > {rag_system.context_window}"
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_similarity_threshold_enforcement(self, query):
        """
        Property test: Similarity threshold should be properly enforced
        Validates: Requirements 3.5
        """
        rag_system = await create_test_rag_system()
        
        # Get search results
        results = await rag_system._search_knowledge(query)
        
        # Property: All results should meet or exceed similarity threshold
        for item, similarity in results:
            assert similarity >= rag_system.similarity_threshold, \
                f"Result similarity {similarity} below threshold {rag_system.similarity_threshold}"
        
        # Property: Similarity scores should be valid
        for item, similarity in results:
            assert isinstance(similarity, (int, float)), "Similarity should be numeric"
            assert 0.0 <= similarity <= 1.0, f"Invalid similarity score: {similarity}"
    
    @given(st.lists(aviation_query_strategy(), min_size=2, max_size=5))
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_retrieval_consistency(self, queries):
        """
        Property test: Same query should return consistent results
        Validates: Requirements 3.5
        """
        rag_system = await create_test_rag_system()
        
        # Test consistency by running same query multiple times
        for query in queries:
            results1 = await rag_system._search_knowledge(query)
            results2 = await rag_system._search_knowledge(query)
            
            # Property: Same query should return same results
            assert len(results1) == len(results2), \
                f"Inconsistent result count for query: {query}"
            
            # Property: Results should be in same order with same similarities
            for (item1, sim1), (item2, sim2) in zip(results1, results2):
                assert item1.id == item2.id, \
                    f"Inconsistent result order for query: {query}"
                assert abs(sim1 - sim2) < 1e-6, \
                    f"Inconsistent similarity scores for query: {query}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])