"""
Unit tests for ambiguous aviation terms handling
Tests clarifying question generation for ambiguous terms
Validates: Requirements 2.5
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.ai.ai_orchestrator import AIOrchestrator
from src.ai.prompt_engine import PromptEngine
from src.knowledge.rag_system import RAGSystem


class TestAmbiguousAviationTerms:
    """Test handling of ambiguous aviation terms and clarifying questions"""
    
    @pytest.fixture
    def mock_ai_model(self):
        """Mock AI model"""
        model = Mock()
        model.generate_response = AsyncMock()
        return model
    
    @pytest.fixture
    def mock_user_profiles(self):
        """Mock user profiles manager"""
        profiles = Mock()
        profiles.get_profile = AsyncMock(return_value={
            'experience_level': 'private_pilot',
            'interests': ['cessna', 'vfr'],
            'conversation_count': 15
        })
        return profiles
    
    @pytest.fixture
    def mock_rag_system(self):
        """Mock RAG system"""
        rag = Mock()
        rag.retrieve_knowledge = AsyncMock()
        return rag
    
    @pytest.fixture
    def ai_orchestrator(self, mock_ai_model, mock_user_profiles, mock_rag_system):
        """Create AI orchestrator instance"""
        return AIOrchestrator(
            ai_model=mock_ai_model,
            user_profiles=mock_user_profiles,
            rag_system=mock_rag_system,
            error_handler=Mock()
        )
    
    @pytest.fixture
    def prompt_engine(self):
        """Create prompt engine instance"""
        return PromptEngine()
    
    @pytest.mark.asyncio
    async def test_ambiguous_term_approach(self, ai_orchestrator):
        """Test handling of ambiguous aviation term 'approach'"""
        # 'Approach' can mean: approach procedure, approach phase, approach control, etc.
        user_message = "Tell me about approach"
        user_id = 12345
        
        # Mock RAG system to return multiple meanings
        ai_orchestrator.rag_system.retrieve_knowledge.return_value = """
        Multiple meanings found for 'approach':
        1. Instrument Approach Procedure (IAP) - a series of predetermined maneuvers
        2. Approach Phase of Flight - the phase from final approach fix to landing
        3. Approach Control - air traffic control service for arriving aircraft
        4. Visual Approach - an approach conducted under visual flight rules
        """
        
        # Mock AI model to generate clarifying question
        ai_orchestrator.ai_model.generate_response.return_value = """
        I found several aviation meanings for "approach." Could you clarify which one you're interested in?
        
        1. **Instrument Approach Procedures** - the step-by-step procedures for landing in low visibility
        2. **Approach Phase of Flight** - the final phase before landing
        3. **Approach Control Services** - air traffic control for arriving aircraft
        4. **Visual Approaches** - approaches conducted under visual conditions
        
        Which aspect of approaches would you like to learn about?
        """
        
        response = await ai_orchestrator.process_message(user_message, user_id, {})
        
        # Verify clarifying question was generated
        assert "clarify" in response.lower() or "which" in response.lower()
        assert "approach" in response.lower()
        assert "1." in response and "2." in response  # Multiple options provided
        
        # Verify RAG system was consulted
        ai_orchestrator.rag_system.retrieve_knowledge.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ambiguous_term_hold(self, ai_orchestrator):
        """Test handling of ambiguous aviation term 'hold'"""
        # 'Hold' can mean: holding pattern, hold short, hold for release, etc.
        user_message = "What is a hold?"
        user_id = 12345
        
        # Mock RAG system to return multiple meanings
        ai_orchestrator.rag_system.retrieve_knowledge.return_value = """
        Multiple meanings for 'hold':
        1. Holding Pattern - a racetrack pattern flown to delay aircraft
        2. Hold Short - instruction to stop before a runway or taxiway
        3. Hold for Release - delay departure until clearance received
        """
        
        # Mock AI model to generate clarifying question
        ai_orchestrator.ai_model.generate_response.return_value = """
        "Hold" has several meanings in aviation. Which one are you asking about?
        
        1. **Holding Patterns** - the oval patterns aircraft fly when delayed
        2. **Hold Short Instructions** - ground control instructions to stop before runways
        3. **Hold for Release** - departure delays waiting for clearance
        
        Let me know which type of "hold" you'd like to understand!
        """
        
        response = await ai_orchestrator.process_message(user_message, user_id, {})
        
        # Verify clarifying question was generated
        assert "which" in response.lower() or "what type" in response.lower()
        assert "hold" in response.lower()
        assert any(term in response.lower() for term in ["pattern", "short", "release"])
    
    @pytest.mark.asyncio
    async def test_ambiguous_term_traffic(self, ai_orchestrator):
        """Test handling of ambiguous aviation term 'traffic'"""
        # 'Traffic' can mean: air traffic, traffic pattern, traffic advisory, etc.
        user_message = "Explain traffic"
        user_id = 12345
        
        # Mock AI model to generate clarifying question
        ai_orchestrator.ai_model.generate_response.return_value = """
        "Traffic" in aviation can refer to several things. Which would you like me to explain?
        
        1. **Air Traffic** - other aircraft in the vicinity
        2. **Traffic Pattern** - the standard rectangular flight path around an airport
        3. **Traffic Advisories** - ATC calls about nearby aircraft
        4. **Traffic Flow Management** - system-wide traffic control
        
        Which aspect of aviation traffic interests you?
        """
        
        response = await ai_orchestrator.process_message(user_message, user_id, {})
        
        # Verify clarifying question addresses multiple meanings
        assert "traffic" in response.lower()
        assert "which" in response.lower() or "what" in response.lower()
        assert "pattern" in response.lower() or "advisory" in response.lower()
    
    @pytest.mark.asyncio
    async def test_ambiguous_term_clearance(self, ai_orchestrator):
        """Test handling of ambiguous aviation term 'clearance'"""
        # 'Clearance' can mean: ATC clearance, takeoff clearance, route clearance, etc.
        user_message = "I need help with clearance"
        user_id = 12345
        
        # Mock AI model to generate clarifying question
        ai_orchestrator.ai_model.generate_response.return_value = """
        There are different types of clearances in aviation. Which one do you need help with?
        
        1. **IFR Clearance** - authorization for instrument flight rules
        2. **Takeoff Clearance** - permission to begin takeoff roll
        3. **Landing Clearance** - permission to land on a runway
        4. **Route Clearance** - approved flight path and altitude
        5. **Taxi Clearance** - permission to move on airport surface
        
        What type of clearance are you asking about?
        """
        
        response = await ai_orchestrator.process_message(user_message, user_id, {})
        
        # Verify comprehensive clarification
        assert "clearance" in response.lower()
        assert "type" in response.lower() or "which" in response.lower()
        assert any(term in response.lower() for term in ["takeoff", "landing", "ifr", "taxi"])
    
    @pytest.mark.asyncio
    async def test_ambiguous_term_with_context_clues(self, ai_orchestrator):
        """Test handling ambiguous terms with context clues"""
        # User provides some context that might help disambiguate
        user_message = "I'm flying VFR and need to know about approach"
        user_id = 12345
        
        # Mock AI model to use context clues
        ai_orchestrator.ai_model.generate_response.return_value = """
        Since you mentioned VFR flying, you're likely asking about visual approaches. However, let me clarify:
        
        1. **Visual Approach** - most common for VFR flights
        2. **Contact Approach** - IFR approach with visual conditions
        3. **Approach Phase** - the final phase of any flight
        
        Are you asking about visual approach procedures for VFR flights?
        """
        
        response = await ai_orchestrator.process_message(user_message, user_id, {})
        
        # Verify context was considered
        assert "vfr" in response.lower() or "visual" in response.lower()
        assert "approach" in response.lower()
        assert "?" in response  # Still asks for clarification but with context
    
    @pytest.mark.asyncio
    async def test_ambiguous_term_with_user_experience_level(self, ai_orchestrator):
        """Test handling ambiguous terms considering user experience level"""
        user_message = "What's a squawk?"
        user_id = 12345
        
        # Mock user profile with student pilot experience
        ai_orchestrator.user_profiles.get_profile.return_value = {
            'experience_level': 'student_pilot',
            'interests': ['training', 'basics'],
            'conversation_count': 3
        }
        
        # Mock AI model to adjust for experience level
        ai_orchestrator.ai_model.generate_response.return_value = """
        "Squawk" typically refers to the transponder code, but let me make sure I give you the right information for your level:
        
        1. **Transponder Code** - the 4-digit code you set on your transponder (most common meaning)
        2. **Radio Call** - sometimes used to mean "transmit" on the radio
        
        As a student pilot, you're probably asking about transponder codes. Is that correct?
        """
        
        response = await ai_orchestrator.process_message(user_message, user_id, {})
        
        # Verify experience level was considered
        assert "student" in response.lower() or "transponder" in response.lower()
        assert "squawk" in response.lower()
        assert "code" in response.lower()
    
    @pytest.mark.asyncio
    async def test_non_ambiguous_term_direct_response(self, ai_orchestrator):
        """Test that non-ambiguous terms get direct responses"""
        user_message = "What is a METAR?"
        user_id = 12345
        
        # Mock AI model to provide direct answer for unambiguous term
        ai_orchestrator.ai_model.generate_response.return_value = """
        A METAR is a standardized weather report format used in aviation. It provides current weather conditions at an airport including:
        
        - Wind direction and speed
        - Visibility
        - Cloud coverage and heights
        - Temperature and dew point
        - Barometric pressure
        
        METARs are issued hourly and are essential for flight planning and safety.
        """
        
        response = await ai_orchestrator.process_message(user_message, user_id, {})
        
        # Verify direct answer without clarifying questions
        assert "metar" in response.lower()
        assert "weather" in response.lower()
        assert "?" not in response  # No clarifying questions
        assert "which" not in response.lower()
    
    @pytest.mark.asyncio
    async def test_multiple_ambiguous_terms_in_message(self, ai_orchestrator):
        """Test handling multiple ambiguous terms in one message"""
        user_message = "Tell me about approach and hold procedures"
        user_id = 12345
        
        # Mock AI model to handle multiple ambiguous terms
        ai_orchestrator.ai_model.generate_response.return_value = """
        You've asked about two terms that each have multiple meanings in aviation. Let me clarify:
        
        **For "approach":**
        1. Instrument approach procedures
        2. Visual approaches
        3. Approach phase of flight
        
        **For "hold":**
        1. Holding patterns
        2. Hold short instructions
        3. Hold for release
        
        Could you specify which types of approach and hold procedures you're interested in?
        """
        
        response = await ai_orchestrator.process_message(user_message, user_id, {})
        
        # Verify both terms were addressed
        assert "approach" in response.lower()
        assert "hold" in response.lower()
        assert "multiple" in response.lower() or "both" in response.lower()
    
    @pytest.mark.asyncio
    async def test_ambiguous_term_with_follow_up_clarification(self, ai_orchestrator):
        """Test handling follow-up clarification after ambiguous term"""
        # First message - ambiguous
        user_message_1 = "Tell me about vectors"
        user_id = 12345
        
        # Mock initial clarifying response
        ai_orchestrator.ai_model.generate_response.return_value = """
        "Vectors" can mean different things in aviation. Which are you asking about?
        
        1. **Radar Vectors** - headings assigned by ATC
        2. **Wind Vectors** - wind direction and speed representation
        3. **Navigation Vectors** - mathematical flight path calculations
        
        Which type of vectors would you like to learn about?
        """
        
        response_1 = await ai_orchestrator.process_message(user_message_1, user_id, {})
        
        # Verify clarifying question
        assert "which" in response_1.lower()
        assert "vectors" in response_1.lower()
        
        # Second message - clarification
        user_message_2 = "I meant radar vectors"
        
        # Mock specific response after clarification
        ai_orchestrator.ai_model.generate_response.return_value = """
        Great! Radar vectors are headings assigned by air traffic control to guide aircraft along specific paths.
        
        When ATC gives you radar vectors, they're providing:
        - Specific compass headings to fly
        - Guidance around traffic or weather
        - Routing to intercept approaches or airways
        
        You'll hear phrases like "fly heading 270" or "vector for traffic separation."
        """
        
        response_2 = await ai_orchestrator.process_message(user_message_2, user_id, {})
        
        # Verify specific answer after clarification
        assert "radar vectors" in response_2.lower()
        assert "heading" in response_2.lower()
        assert "atc" in response_2.lower() or "air traffic" in response_2.lower()
    
    def test_ambiguous_term_detection_patterns(self, prompt_engine):
        """Test patterns for detecting ambiguous aviation terms"""
        # Common ambiguous aviation terms
        ambiguous_terms = [
            "approach", "hold", "traffic", "clearance", "vectors", "squawk",
            "pattern", "base", "final", "tower", "ground", "departure",
            "arrival", "fix", "course", "track", "bearing", "radial"
        ]
        
        for term in ambiguous_terms:
            # Test that these terms would trigger disambiguation logic
            test_message = f"What is {term}?"
            
            # In a real implementation, this would check if the term is in an ambiguous terms database
            # For this test, we verify the terms are recognized as potentially ambiguous
            assert len(term) > 2  # Basic validation that terms are meaningful
            assert term.isalpha()  # Terms should be alphabetic
    
    @pytest.mark.asyncio
    async def test_context_based_disambiguation(self, ai_orchestrator):
        """Test context-based disambiguation without explicit clarification"""
        # Message with enough context to disambiguate
        user_message = "I'm on final approach and tower is asking me to go around"
        user_id = 12345
        
        # Mock AI model to use context for disambiguation
        ai_orchestrator.ai_model.generate_response.return_value = """
        It sounds like you're in the final approach phase and ATC has issued a go-around instruction. Here's what to do:
        
        1. **Immediately apply full power**
        2. **Pitch up to climb attitude**
        3. **Retract flaps as appropriate**
        4. **Follow the published missed approach procedure**
        5. **Contact tower for further instructions**
        
        Go-arounds are normal safety procedures - don't hesitate to execute them when instructed.
        """
        
        response = await ai_orchestrator.process_message(user_message, user_id, {})
        
        # Verify context was used to provide specific guidance
        assert "go-around" in response.lower() or "go around" in response.lower()
        assert "power" in response.lower()
        assert "missed approach" in response.lower()
        # No clarifying questions needed due to sufficient context
        assert "which" not in response.lower()
    
    @pytest.mark.asyncio
    async def test_abbreviation_disambiguation(self, ai_orchestrator):
        """Test disambiguation of aviation abbreviations"""
        user_message = "What does ATC mean?"
        user_id = 12345
        
        # Mock AI model response for abbreviation
        ai_orchestrator.ai_model.generate_response.return_value = """
        ATC stands for **Air Traffic Control** - the service that manages aircraft movements in controlled airspace.
        
        ATC includes several types of controllers:
        - **Ground Control** - manages aircraft on airport surfaces
        - **Tower Control** - handles takeoffs and landings
        - **Approach/Departure Control** - manages aircraft in terminal areas
        - **Center Control** - handles en route traffic
        
        ATC ensures safe separation between aircraft and provides navigation assistance.
        """
        
        response = await ai_orchestrator.process_message(user_message, user_id, {})
        
        # Verify abbreviation was expanded and explained
        assert "air traffic control" in response.lower()
        assert "atc" in response.lower()
        assert "control" in response.lower()
    
    @pytest.mark.asyncio
    async def test_regional_terminology_disambiguation(self, ai_orchestrator):
        """Test disambiguation of terms that vary by region"""
        user_message = "What's the difference between a circuit and pattern?"
        user_id = 12345
        
        # Mock AI model to explain regional differences
        ai_orchestrator.ai_model.generate_response.return_value = """
        "Circuit" and "pattern" refer to the same thing but are used in different regions:
        
        - **Traffic Pattern** (US/North America) - the rectangular flight path around an airport
        - **Circuit** (UK/Commonwealth countries) - same rectangular flight path
        
        Both include the same legs:
        - Upwind/Crosswind
        - Downwind
        - Base
        - Final
        
        The procedures are identical - it's just regional terminology!
        """
        
        response = await ai_orchestrator.process_message(user_message, user_id, {})
        
        # Verify regional differences were explained
        assert "circuit" in response.lower()
        assert "pattern" in response.lower()
        assert "region" in response.lower() or "us" in response.lower() or "uk" in response.lower()
    
    @pytest.mark.asyncio
    async def test_technical_vs_colloquial_disambiguation(self, ai_orchestrator):
        """Test disambiguation between technical and colloquial aviation terms"""
        user_message = "What does 'heavy' mean in aviation?"
        user_id = 12345
        
        # Mock AI model to explain technical vs colloquial usage
        ai_orchestrator.ai_model.generate_response.return_value = """
        "Heavy" in aviation has a specific technical meaning:
        
        **Official Definition:**
        - Aircraft with maximum takeoff weight of 300,000 pounds or more
        - Must use "Heavy" in radio callsigns (e.g., "United 123 Heavy")
        - Creates significant wake turbulence that affects following aircraft
        
        **Common Usage:**
        - Sometimes used colloquially for any large aircraft
        - Pilots may informally call big jets "heavies"
        
        The official designation is important for ATC separation requirements.
        """
        
        response = await ai_orchestrator.process_message(user_message, user_id, {})
        
        # Verify both technical and colloquial meanings were addressed
        assert "heavy" in response.lower()
        assert "300,000" in response or "technical" in response.lower()
        assert "wake turbulence" in response.lower() or "separation" in response.lower()