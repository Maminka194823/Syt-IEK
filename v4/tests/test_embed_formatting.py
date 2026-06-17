"""
Property-based tests for embed formatting consistency
Feature: aviation-discord-bot, Property 8: Discord Embed Formatting Consistency
"""

import pytest
import discord
from unittest.mock import MagicMock
from hypothesis import given, strategies as st, settings
from typing import Dict, Any

# Import the components we're testing
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from bot.embed_builder import EmbedBuilder


def create_embed_builder():
    """Create an embed builder for testing"""
    return EmbedBuilder()


# Property-based test strategies
@st.composite
def weather_data_strategy(draw):
    """Generate realistic weather data for testing"""
    airport_codes = ["KJFK", "KLAX", "KORD", "KDEN", "KBOS", "KSEA", "KMIA", "KPHX"]
    flight_categories = ["VFR", "MVFR", "IFR", "LIFR"]
    
    return {
        "airport_code": draw(st.sampled_from(airport_codes)),
        "conditions": {
            "flight_category": draw(st.sampled_from(flight_categories)),
            "visibility": draw(st.floats(min_value=0.1, max_value=10.0)),
            "ceiling": draw(st.one_of(
                st.just("CLR"),
                st.just("SKC"),
                st.integers(min_value=100, max_value=10000)
            )),
            "wind": {
                "direction": draw(st.integers(min_value=0, max_value=360)),
                "speed": draw(st.integers(min_value=0, max_value=50)),
                "gust": draw(st.one_of(st.none(), st.integers(min_value=15, max_value=80)))
            },
            "temperature": draw(st.integers(min_value=-40, max_value=50)),
            "dewpoint": draw(st.integers(min_value=-40, max_value=50)),
            "altimeter": draw(st.floats(min_value=28.00, max_value=31.50))
        },
        "metar_raw": draw(st.text(min_size=20, max_size=200)),
        "taf_raw": draw(st.one_of(st.none(), st.text(min_size=50, max_size=500)))
    }


@st.composite
def aircraft_data_strategy(draw):
    """Generate realistic aircraft data for testing"""
    manufacturers = ["Cessna", "Piper", "Beechcraft", "Cirrus", "Boeing", "Airbus"]
    categories = ["airplane", "helicopter", "glider"]
    
    return {
        "aircraft_type": draw(st.text(min_size=3, max_size=50)),
        "manufacturer": draw(st.sampled_from(manufacturers)),
        "model": draw(st.text(min_size=2, max_size=20)),
        "category": draw(st.sampled_from(categories)),
        "specifications": {
            "max_speed": draw(st.integers(min_value=50, max_value=600)),
            "cruise_speed": draw(st.integers(min_value=40, max_value=500)),
            "service_ceiling": draw(st.integers(min_value=5000, max_value=50000)),
            "range": draw(st.integers(min_value=100, max_value=5000)),
            "fuel_capacity": draw(st.integers(min_value=10, max_value=1000)),
            "max_takeoff_weight": draw(st.integers(min_value=500, max_value=100000)),
            "empty_weight": draw(st.integers(min_value=300, max_value=80000)),
            "useful_load": draw(st.integers(min_value=200, max_value=50000)),
            "engine_type": draw(st.text(min_size=5, max_size=50)),
            "engine_power": draw(st.integers(min_value=50, max_value=5000))
        },
        "operating_limits": {
            "vne": draw(st.integers(min_value=80, max_value=400)),
            "va": draw(st.integers(min_value=60, max_value=300)),
            "vfe": draw(st.integers(min_value=50, max_value=200))
        },
        "certification_info": {
            "certification_basis": draw(st.text(min_size=10, max_size=100))
        }
    }


@st.composite
def regulation_data_strategy(draw):
    """Generate realistic regulation data for testing"""
    return {
        "title": draw(st.text(min_size=10, max_size=100)),
        "number": draw(st.text(min_size=3, max_size=20)),
        "content": draw(st.text(min_size=50, max_size=2000)),
        "source": draw(st.text(min_size=5, max_size=50)),
        "applicability": draw(st.text(min_size=10, max_size=100)),
        "effective_date": draw(st.text(min_size=8, max_size=20)),
        "related_regulations": draw(st.lists(st.text(min_size=3, max_size=20), min_size=0, max_size=10))
    }


@st.composite
def flight_plan_data_strategy(draw):
    """Generate realistic flight plan data for testing"""
    airport_codes = ["KJFK", "KLAX", "KORD", "KDEN", "KBOS", "KSEA", "KMIA", "KPHX"]
    
    return {
        "departure": draw(st.sampled_from(airport_codes)),
        "destination": draw(st.sampled_from(airport_codes)),
        "route": draw(st.text(min_size=10, max_size=200)),
        "distance": draw(st.integers(min_value=10, max_value=3000)),
        "estimated_time": draw(st.text(min_size=4, max_size=10)),
        "altitude": draw(st.integers(min_value=1000, max_value=45000)),
        "fuel": {
            "required": draw(st.integers(min_value=5, max_value=500)),
            "reserves": draw(st.integers(min_value=2, max_value=100)),
            "total": draw(st.integers(min_value=10, max_value=600))
        },
        "weather_summary": draw(st.text(min_size=20, max_size=200)),
        "notams": draw(st.lists(st.text(min_size=10, max_size=100), min_size=0, max_size=5))
    }


class MockDiscordUser:
    """Mock Discord user for testing"""
    
    def __init__(self, display_name: str = "TestUser"):
        self.display_name = display_name
        self.avatar = None


class TestEmbedFormattingConsistency:
    """
    Property 8: Discord Embed Formatting Consistency
    For any aviation data type (weather, aircraft, regulations, flight planning),
    the embed builder should create structured, consistently themed embeds with
    appropriate color coding, organized layouts, and required information fields.
    """
    
    @given(weather_data_strategy())
    @settings(max_examples=100, deadline=10000)
    @pytest.mark.asyncio
    async def test_weather_embed_consistency(self, weather_data):
        """
        Property test: Weather embeds should have consistent structure and formatting
        Validates: Requirements 1.2, 6.1, 6.2, 6.3, 6.4, 6.6
        """
        embed_builder = create_embed_builder()
        
        # Generate weather embed
        embed = embed_builder.create_weather_embed(weather_data)
        
        # Property: Embed should be a valid Discord embed
        assert isinstance(embed, discord.Embed), "Weather embed should be Discord Embed instance"
        
        # Property: Embed should have a title with weather emoji
        assert embed.title is not None, "Weather embed should have a title"
        assert "🌤️" in embed.title or "Weather" in embed.title, "Weather embed title should contain weather indicator"
        
        # Property: Color should be appropriate for flight category
        flight_category = weather_data.get("conditions", {}).get("flight_category", "UNKNOWN")
        if flight_category == "VFR":
            assert embed.color.value == embed_builder.colors["weather_vfr"], "VFR weather should use green color"
        elif flight_category == "MVFR":
            assert embed.color.value == embed_builder.colors["weather_mvfr"], "MVFR weather should use orange color"
        elif flight_category in ["IFR", "LIFR"]:
            assert embed.color.value == embed_builder.colors["weather_ifr"], "IFR weather should use red color"
        
        # Property: Embed should have timestamp
        assert embed.timestamp is not None, "Weather embed should have timestamp"
        
        # Property: Embed should have fields for key weather information
        field_names = [field.name.lower() for field in embed.fields]
        assert any("flight category" in name for name in field_names), "Weather embed should have flight category field"
        
        # Property: Embed should not exceed Discord limits
        assert len(embed.title) <= 256, "Embed title should not exceed Discord limit"
        assert len(embed.fields) <= 25, "Embed should not exceed Discord field limit"
        
        for field in embed.fields:
            assert len(field.name) <= 256, "Field name should not exceed Discord limit"
            assert len(field.value) <= 1024, "Field value should not exceed Discord limit"
    
    @given(aircraft_data_strategy())
    @settings(max_examples=100, deadline=10000)
    @pytest.mark.asyncio
    async def test_aircraft_embed_consistency(self, aircraft_data):
        """
        Property test: Aircraft embeds should have consistent structure and formatting
        Validates: Requirements 1.2, 6.1, 6.2, 6.3, 6.4, 6.6
        """
        embed_builder = create_embed_builder()
        
        # Generate aircraft embed
        embed = embed_builder.create_aircraft_embed(aircraft_data)
        
        # Property: Embed should be a valid Discord embed
        assert isinstance(embed, discord.Embed), "Aircraft embed should be Discord Embed instance"
        
        # Property: Embed should have a title with aircraft emoji
        assert embed.title is not None, "Aircraft embed should have a title"
        assert "✈️" in embed.title, "Aircraft embed title should contain aircraft emoji"
        
        # Property: Color should be aircraft-themed
        assert embed.color.value == embed_builder.colors["aircraft"], "Aircraft embed should use aircraft color"
        
        # Property: Embed should have timestamp
        assert embed.timestamp is not None, "Aircraft embed should have timestamp"
        
        # Property: Embed should not exceed Discord limits
        assert len(embed.title) <= 256, "Embed title should not exceed Discord limit"
        assert len(embed.fields) <= 25, "Embed should not exceed Discord field limit"
        
        for field in embed.fields:
            assert len(field.name) <= 256, "Field name should not exceed Discord limit"
            assert len(field.value) <= 1024, "Field value should not exceed Discord limit"
        
        # Property: Specifications should be properly formatted
        field_names = [field.name.lower() for field in embed.fields]
        specs = aircraft_data.get("specifications", {})
        
        if "max_speed" in specs:
            assert any("speed" in name for name in field_names), "Aircraft embed should include speed information"
        
        if "service_ceiling" in specs:
            assert any("ceiling" in name for name in field_names), "Aircraft embed should include ceiling information"
    
    @given(regulation_data_strategy())
    @settings(max_examples=100, deadline=10000)
    @pytest.mark.asyncio
    async def test_regulation_embed_consistency(self, regulation_data):
        """
        Property test: Regulation embeds should have consistent structure and formatting
        Validates: Requirements 1.2, 6.1, 6.2, 6.3, 6.4, 6.6
        """
        embed_builder = create_embed_builder()
        
        # Generate regulation embed
        embed = embed_builder.create_regulation_embed(regulation_data)
        
        # Property: Embed should be a valid Discord embed
        assert isinstance(embed, discord.Embed), "Regulation embed should be Discord Embed instance"
        
        # Property: Embed should have a title with regulation emoji
        assert embed.title is not None, "Regulation embed should have a title"
        assert "📋" in embed.title, "Regulation embed title should contain regulation emoji"
        
        # Property: Color should be regulation-themed
        assert embed.color.value == embed_builder.colors["regulation"], "Regulation embed should use regulation color"
        
        # Property: Embed should have timestamp
        assert embed.timestamp is not None, "Regulation embed should have timestamp"
        
        # Property: Embed should not exceed Discord limits
        assert len(embed.title) <= 256, "Embed title should not exceed Discord limit"
        assert len(embed.fields) <= 25, "Embed should not exceed Discord field limit"
        
        for field in embed.fields:
            assert len(field.name) <= 256, "Field name should not exceed Discord limit"
            assert len(field.value) <= 1024, "Field value should not exceed Discord limit"
        
        # Property: Long content should be properly sectioned
        content = regulation_data.get("content", "")
        if len(content) > 1000:
            field_names = [field.name.lower() for field in embed.fields]
            assert any("section" in name for name in field_names), "Long regulation content should be sectioned"
    
    @given(flight_plan_data_strategy())
    @settings(max_examples=100, deadline=10000)
    @pytest.mark.asyncio
    async def test_flight_plan_embed_consistency(self, flight_plan_data):
        """
        Property test: Flight plan embeds should have consistent structure and formatting
        Validates: Requirements 1.2, 6.1, 6.2, 6.3, 6.4, 6.6
        """
        embed_builder = create_embed_builder()
        
        # Generate flight plan embed
        embed = embed_builder.create_flight_planning_embed(flight_plan_data)
        
        # Property: Embed should be a valid Discord embed
        assert isinstance(embed, discord.Embed), "Flight plan embed should be Discord Embed instance"
        
        # Property: Embed should have a title with navigation emoji
        assert embed.title is not None, "Flight plan embed should have a title"
        assert "🧭" in embed.title, "Flight plan embed title should contain navigation emoji"
        
        # Property: Color should be primary themed
        assert embed.color.value == embed_builder.colors["primary"], "Flight plan embed should use primary color"
        
        # Property: Embed should have timestamp
        assert embed.timestamp is not None, "Flight plan embed should have timestamp"
        
        # Property: Title should include departure and destination
        departure = flight_plan_data.get("departure", "")
        destination = flight_plan_data.get("destination", "")
        assert departure in embed.title, "Flight plan title should include departure airport"
        assert destination in embed.title, "Flight plan title should include destination airport"
        
        # Property: Embed should not exceed Discord limits
        assert len(embed.title) <= 256, "Embed title should not exceed Discord limit"
        assert len(embed.fields) <= 25, "Embed should not exceed Discord field limit"
        
        for field in embed.fields:
            assert len(field.name) <= 256, "Field name should not exceed Discord limit"
            assert len(field.value) <= 1024, "Field value should not exceed Discord limit"
    
    @given(st.text(min_size=1, max_size=100), st.text(min_size=1, max_size=500))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_error_embed_consistency(self, title, description):
        """
        Property test: Error embeds should have consistent structure and formatting
        Validates: Requirements 1.2, 6.5
        """
        embed_builder = create_embed_builder()
        
        # Generate error embed
        embed = embed_builder.create_error_embed(title, description)
        
        # Property: Embed should be a valid Discord embed
        assert isinstance(embed, discord.Embed), "Error embed should be Discord Embed instance"
        
        # Property: Embed should have a title with danger emoji
        assert embed.title is not None, "Error embed should have a title"
        assert "🚨" in embed.title, "Error embed title should contain danger emoji"
        
        # Property: Color should be danger-themed
        assert embed.color.value == embed_builder.colors["danger"], "Error embed should use danger color"
        
        # Property: Embed should have timestamp
        assert embed.timestamp is not None, "Error embed should have timestamp"
        
        # Property: Embed should have helpful suggestions
        field_names = [field.name.lower() for field in embed.fields]
        assert any("what you can do" in name for name in field_names), "Error embed should provide helpful suggestions"
        
        # Property: Embed should not exceed Discord limits
        assert len(embed.title) <= 256, "Embed title should not exceed Discord limit"
        assert len(embed.description) <= 2048, "Embed description should not exceed Discord limit"
    
    @given(st.text(min_size=1, max_size=100), st.text(min_size=1, max_size=500))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_info_embed_consistency(self, title, description):
        """
        Property test: Info embeds should have consistent structure and formatting
        Validates: Requirements 1.2, 6.1
        """
        embed_builder = create_embed_builder()
        
        # Generate info embed
        embed = embed_builder.create_info_embed(title, description)
        
        # Property: Embed should be a valid Discord embed
        assert isinstance(embed, discord.Embed), "Info embed should be Discord Embed instance"
        
        # Property: Embed should have a title with info emoji
        assert embed.title is not None, "Info embed should have a title"
        assert "ℹ️" in embed.title, "Info embed title should contain info emoji"
        
        # Property: Color should be info-themed
        assert embed.color.value == embed_builder.colors["info"], "Info embed should use info color"
        
        # Property: Embed should have timestamp
        assert embed.timestamp is not None, "Info embed should have timestamp"
        
        # Property: Embed should not exceed Discord limits
        assert len(embed.title) <= 256, "Embed title should not exceed Discord limit"
        assert len(embed.description) <= 2048, "Embed description should not exceed Discord limit"
    
    @given(st.text(min_size=1, max_size=2000))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_response_embed_consistency(self, response_text):
        """
        Property test: Response embeds should have consistent structure and formatting
        Validates: Requirements 1.2, 6.1, 6.2, 6.3, 6.4, 6.6
        """
        embed_builder = create_embed_builder()
        mock_user = MockDiscordUser()
        
        # Generate response embed
        embed = embed_builder.create_response_embed(response_text, mock_user)
        
        # Property: Embed should be a valid Discord embed
        assert isinstance(embed, discord.Embed), "Response embed should be Discord Embed instance"
        
        # Property: Embed should have a title
        assert embed.title is not None, "Response embed should have a title"
        
        # Property: Embed should have appropriate color based on content
        assert embed.color is not None, "Response embed should have a color"
        assert embed.color.value in embed_builder.colors.values(), "Response embed should use predefined colors"
        
        # Property: Embed should have timestamp
        assert embed.timestamp is not None, "Response embed should have timestamp"
        
        # Property: Embed should have footer with user information
        assert embed.footer is not None, "Response embed should have footer"
        assert mock_user.display_name in embed.footer.text, "Response embed footer should include user name"
        
        # Property: Long responses should be truncated appropriately
        if len(response_text) > 2000:
            assert len(embed.description) <= 2000, "Long response should be truncated"
            assert "..." in embed.description, "Truncated response should indicate truncation"
        
        # Property: Embed should not exceed Discord limits
        assert len(embed.title) <= 256, "Embed title should not exceed Discord limit"
        assert len(embed.description) <= 2048, "Embed description should not exceed Discord limit"
    
    @given(st.lists(st.dictionaries(
        keys=st.sampled_from(["weather", "aircraft", "regulation", "flight_plan"]),
        values=st.text(min_size=10, max_size=100)
    ), min_size=1, max_size=5))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_embed_color_consistency(self, data_types):
        """
        Property test: Embed colors should be consistent across data types
        Same data type should always use same color scheme
        """
        embed_builder = create_embed_builder()
        
        # Test color consistency for each data type
        for data_type_dict in data_types:
            for data_type, content in data_type_dict.items():
                if data_type == "weather":
                    # Test different flight categories use appropriate colors
                    for category in ["VFR", "MVFR", "IFR"]:
                        weather_data = {
                            "airport_code": "KTEST",
                            "conditions": {"flight_category": category}
                        }
                        embed = embed_builder.create_weather_embed(weather_data)
                        
                        if category == "VFR":
                            expected_color = embed_builder.colors["weather_vfr"]
                        elif category == "MVFR":
                            expected_color = embed_builder.colors["weather_mvfr"]
                        else:  # IFR
                            expected_color = embed_builder.colors["weather_ifr"]
                        
                        assert embed.color.value == expected_color, \
                            f"Weather embed for {category} should use consistent color"
                
                elif data_type == "aircraft":
                    aircraft_data = {"aircraft_type": content}
                    embed = embed_builder.create_aircraft_embed(aircraft_data)
                    assert embed.color.value == embed_builder.colors["aircraft"], \
                        "Aircraft embeds should use consistent color"
                
                elif data_type == "regulation":
                    regulation_data = {"title": content}
                    embed = embed_builder.create_regulation_embed(regulation_data)
                    assert embed.color.value == embed_builder.colors["regulation"], \
                        "Regulation embeds should use consistent color"
                
                elif data_type == "flight_plan":
                    flight_plan_data = {"departure": "KTEST", "destination": "KTEST2"}
                    embed = embed_builder.create_flight_planning_embed(flight_plan_data)
                    assert embed.color.value == embed_builder.colors["primary"], \
                        "Flight plan embeds should use consistent color"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])