"""
V4 Embed Builder
Creates aviation-themed Discord embeds with consistent formatting
Handles weather, aircraft, regulation, and flight planning displays
"""

import discord
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

class EmbedBuilder:
    """
    Creates rich Discord embeds for aviation data presentation
    Implements consistent color schemes and formatting patterns
    """
    
    def __init__(self):
        # Aviation-themed color scheme
        self.colors = {
            "primary": 0x1E88E5,      # Aviation blue
            "success": 0x4CAF50,      # Green for good conditions
            "warning": 0xFF9800,      # Orange for caution
            "danger": 0xF44336,       # Red for dangerous conditions
            "info": 0x2196F3,         # Light blue for information
            "neutral": 0x607D8B,      # Gray for neutral information
            "weather_vfr": 0x4CAF50,  # Green for VFR conditions
            "weather_mvfr": 0xFF9800, # Orange for MVFR conditions
            "weather_ifr": 0xF44336,  # Red for IFR conditions
            "aircraft": 0x795548,     # Brown for aircraft information
            "regulation": 0x9C27B0    # Purple for regulations
        }
        
        # Common aviation emojis
        self.emojis = {
            "aircraft": "✈️",
            "weather": "🌤️",
            "airport": "🛫",
            "navigation": "🧭",
            "fuel": "⛽",
            "altitude": "📏",
            "speed": "💨",
            "warning": "⚠️",
            "danger": "🚨",
            "success": " ",
            "info": "ℹ️",
            "regulation": "📋",
            "radio": "📻",
            "runway": "🛬"
        }
    
    def create_weather_embed(self, weather_data: Dict[str, Any]) -> discord.Embed:
        """
        Create structured weather embed with color-coded conditions
        Formats METAR/TAF data with organized field layouts
        """
        # Determine weather conditions and color
        conditions = weather_data.get("conditions", {})
        flight_category = conditions.get("flight_category", "UNKNOWN").upper()
        
        color = self.colors["neutral"]
        if flight_category == "VFR":
            color = self.colors["weather_vfr"]
        elif flight_category == "MVFR":
            color = self.colors["weather_mvfr"]
        elif flight_category in ["IFR", "LIFR"]:
            color = self.colors["weather_ifr"]
        
        # Create embed
        airport_code = weather_data.get("airport_code", "UNKNOWN")
        embed = discord.Embed(
            title=f"{self.emojis['weather']} Weather Report - {airport_code}",
            color=color,
            timestamp=datetime.utcnow()
        )
        
        # Flight category with appropriate emoji
        category_emoji = self.emojis["success"] if flight_category == "VFR" else \
                        self.emojis["warning"] if flight_category == "MVFR" else \
                        self.emojis["danger"]
        
        embed.add_field(
            name=f"{category_emoji} Flight Category",
            value=flight_category,
            inline=True
        )
        
        # Current conditions
        if "visibility" in conditions:
            embed.add_field(
                name="👁️ Visibility",
                value=f"{conditions['visibility']} SM",
                inline=True
            )
        
        if "ceiling" in conditions:
            ceiling = conditions["ceiling"]
            if ceiling == "CLR" or ceiling == "SKC":
                embed.add_field(name="☁️ Ceiling", value="Clear", inline=True)
            else:
                embed.add_field(name="☁️ Ceiling", value=f"{ceiling} ft", inline=True)
        
        # Wind information
        if "wind" in conditions:
            wind = conditions["wind"]
            wind_text = f"{wind.get('direction', '000')}° at {wind.get('speed', '0')} kt"
            if wind.get("gust"):
                wind_text += f" gusting {wind['gust']} kt"
            
            embed.add_field(
                name=f"{self.emojis['speed']} Wind",
                value=wind_text,
                inline=True
            )
        
        # Temperature and dewpoint
        if "temperature" in conditions:
            temp_text = f"{conditions['temperature']}°C"
            if "dewpoint" in conditions:
                temp_text += f" / {conditions['dewpoint']}°C"
            
            embed.add_field(
                name="🌡️ Temperature",
                value=temp_text,
                inline=True
            )
        
        # Altimeter setting
        if "altimeter" in conditions:
            embed.add_field(
                name=f"{self.emojis['altitude']} Altimeter",
                value=f"{conditions['altimeter']} inHg",
                inline=True
            )
        
        # Raw METAR
        if "metar_raw" in weather_data:
            embed.add_field(
                name="📡 Raw METAR",
                value=f"```{weather_data['metar_raw']}```",
                inline=False
            )
        
        # TAF if available
        if "taf_raw" in weather_data and weather_data["taf_raw"]:
            taf_text = weather_data["taf_raw"]
            if len(taf_text) > 1000:  # Truncate long TAFs
                taf_text = taf_text[:1000] + "..."
            
            embed.add_field(
                name="📋 Terminal Forecast (TAF)",
                value=f"```{taf_text}```",
                inline=False
            )
        
        # Footer with data source and timestamp
        embed.set_footer(
            text=f"Data from aviation weather services • Updated",
            icon_url="https://cdn.discordapp.com/emojis/weather_icon.png"
        )
        
        return embed
    
    def create_aircraft_embed(self, aircraft_data: Dict[str, Any]) -> discord.Embed:
        """
        Create structured aircraft specification display
        Formats performance data and images in clear, readable embeds
        """
        aircraft_type = aircraft_data.get("aircraft_type", "Unknown Aircraft")
        manufacturer = aircraft_data.get("manufacturer", "")
        model = aircraft_data.get("model", "")
        
        title = f"{self.emojis['aircraft']} {aircraft_type}"
        if manufacturer and model:
            title = f"{self.emojis['aircraft']} {manufacturer} {model}"
        
        embed = discord.Embed(
            title=title,
            color=self.colors["aircraft"],
            timestamp=datetime.utcnow()
        )
        
        # Basic information
        if "category" in aircraft_data:
            embed.add_field(
                name="📂 Category",
                value=aircraft_data["category"].title(),
                inline=True
            )
        
        # Specifications
        specs = aircraft_data.get("specifications", {})
        
        if "max_speed" in specs:
            embed.add_field(
                name=f"{self.emojis['speed']} Max Speed",
                value=f"{specs['max_speed']} kt",
                inline=True
            )
        
        if "cruise_speed" in specs:
            embed.add_field(
                name=f"{self.emojis['speed']} Cruise Speed",
                value=f"{specs['cruise_speed']} kt",
                inline=True
            )
        
        if "service_ceiling" in specs:
            embed.add_field(
                name=f"{self.emojis['altitude']} Service Ceiling",
                value=f"{specs['service_ceiling']:,} ft",
                inline=True
            )
        
        if "range" in specs:
            embed.add_field(
                name="🗺️ Range",
                value=f"{specs['range']} nm",
                inline=True
            )
        
        if "fuel_capacity" in specs:
            embed.add_field(
                name=f"{self.emojis['fuel']} Fuel Capacity",
                value=f"{specs['fuel_capacity']} gal",
                inline=True
            )
        
        # Weight and balance
        if "max_takeoff_weight" in specs:
            embed.add_field(
                name="⚖️ Max Takeoff Weight",
                value=f"{specs['max_takeoff_weight']:,} lbs",
                inline=True
            )
        
        if "empty_weight" in specs:
            embed.add_field(
                name="⚖️ Empty Weight",
                value=f"{specs['empty_weight']:,} lbs",
                inline=True
            )
        
        if "useful_load" in specs:
            embed.add_field(
                name="⚖️ Useful Load",
                value=f"{specs['useful_load']:,} lbs",
                inline=True
            )
        
        # Engine information
        if "engine_type" in specs:
            engine_text = specs["engine_type"]
            if "engine_power" in specs:
                engine_text += f" - {specs['engine_power']} HP"
            
            embed.add_field(
                name="🔧 Engine",
                value=engine_text,
                inline=False
            )
        
        # Operating limits
        limits = aircraft_data.get("operating_limits", {})
        if limits:
            limits_text = []
            if "vne" in limits:
                limits_text.append(f"VNE: {limits['vne']} kt")
            if "va" in limits:
                limits_text.append(f"VA: {limits['va']} kt")
            if "vfe" in limits:
                limits_text.append(f"VFE: {limits['vfe']} kt")
            
            if limits_text:
                embed.add_field(
                    name=f"{self.emojis['warning']} Operating Limits",
                    value=" • ".join(limits_text),
                    inline=False
                )
        
        # Certification info
        cert_info = aircraft_data.get("certification_info", {})
        if "certification_basis" in cert_info:
            embed.add_field(
                name=f"{self.emojis['regulation']} Certification",
                value=cert_info["certification_basis"],
                inline=False
            )
        
        embed.set_footer(text="Aircraft specifications from aviation databases")
        
        return embed
    
    def create_regulation_embed(self, regulation_data: Dict[str, Any]) -> discord.Embed:
        """
        Create organized regulatory information display
        Presents complex FAR text in digestible sections with proper citations
        """
        regulation_title = regulation_data.get("title", "Aviation Regulation")
        regulation_number = regulation_data.get("number", "")
        
        title = f"{self.emojis['regulation']} {regulation_title}"
        if regulation_number:
            title = f"{self.emojis['regulation']} {regulation_number}: {regulation_title}"
        
        embed = discord.Embed(
            title=title,
            color=self.colors["regulation"],
            timestamp=datetime.utcnow()
        )
        
        # Regulation content
        content = regulation_data.get("content", "")
        if content:
            # Split long content into sections
            if len(content) > 1000:
                # Try to split at paragraph breaks
                paragraphs = content.split('\n\n')
                current_section = ""
                section_count = 1
                
                for paragraph in paragraphs:
                    if len(current_section + paragraph) > 900:
                        if current_section:
                            embed.add_field(
                                name=f"📄 Section {section_count}",
                                value=current_section.strip(),
                                inline=False
                            )
                            section_count += 1
                            current_section = paragraph + "\n\n"
                        else:
                            # Single paragraph too long, truncate
                            embed.add_field(
                                name=f"📄 Section {section_count}",
                                value=paragraph[:900] + "...",
                                inline=False
                            )
                            section_count += 1
                    else:
                        current_section += paragraph + "\n\n"
                
                if current_section:
                    embed.add_field(
                        name=f"📄 Section {section_count}",
                        value=current_section.strip(),
                        inline=False
                    )
            else:
                embed.add_field(
                    name="📄 Regulation Text",
                    value=content,
                    inline=False
                )
        
        # Source and applicability
        if "source" in regulation_data:
            embed.add_field(
                name="📚 Source",
                value=regulation_data["source"],
                inline=True
            )
        
        if "applicability" in regulation_data:
            embed.add_field(
                name="🎯 Applicability",
                value=regulation_data["applicability"],
                inline=True
            )
        
        if "effective_date" in regulation_data:
            embed.add_field(
                name="📅 Effective Date",
                value=regulation_data["effective_date"],
                inline=True
            )
        
        # Related regulations
        if "related_regulations" in regulation_data:
            related = regulation_data["related_regulations"]
            if isinstance(related, list):
                related_text = " • ".join(related[:5])  # Limit to 5 related regs
                embed.add_field(
                    name="🔗 Related Regulations",
                    value=related_text,
                    inline=False
                )
        
        embed.set_footer(text="Regulation information from FAA sources")
        
        return embed
    
    def create_flight_planning_embed(self, flight_plan_data: Dict[str, Any]) -> discord.Embed:
        """
        Create flight planning information display
        Shows route details, fuel calculations, and weather summaries
        """
        departure = flight_plan_data.get("departure", "UNKNOWN")
        destination = flight_plan_data.get("destination", "UNKNOWN")
        
        embed = discord.Embed(
            title=f"{self.emojis['navigation']} Flight Plan: {departure} → {destination}",
            color=self.colors["primary"],
            timestamp=datetime.utcnow()
        )
        
        # Route information
        if "route" in flight_plan_data:
            route = flight_plan_data["route"]
            embed.add_field(
                name="🗺️ Route",
                value=route if len(route) < 100 else route[:100] + "...",
                inline=False
            )
        
        if "distance" in flight_plan_data:
            embed.add_field(
                name="📏 Distance",
                value=f"{flight_plan_data['distance']} nm",
                inline=True
            )
        
        if "estimated_time" in flight_plan_data:
            embed.add_field(
                name="⏱️ Estimated Time",
                value=flight_plan_data["estimated_time"],
                inline=True
            )
        
        if "altitude" in flight_plan_data:
            embed.add_field(
                name=f"{self.emojis['altitude']} Planned Altitude",
                value=f"{flight_plan_data['altitude']} ft",
                inline=True
            )
        
        # Fuel calculations
        fuel_data = flight_plan_data.get("fuel", {})
        if fuel_data:
            if "required" in fuel_data:
                embed.add_field(
                    name=f"{self.emojis['fuel']} Fuel Required",
                    value=f"{fuel_data['required']} gal",
                    inline=True
                )
            
            if "reserves" in fuel_data:
                embed.add_field(
                    name=f"{self.emojis['fuel']} Reserves",
                    value=f"{fuel_data['reserves']} gal",
                    inline=True
                )
            
            if "total" in fuel_data:
                embed.add_field(
                    name=f"{self.emojis['fuel']} Total Fuel",
                    value=f"{fuel_data['total']} gal",
                    inline=True
                )
        
        # Weather summary
        if "weather_summary" in flight_plan_data:
            weather = flight_plan_data["weather_summary"]
            embed.add_field(
                name=f"{self.emojis['weather']} Weather Summary",
                value=weather,
                inline=False
            )
        
        # NOTAMs or special considerations
        if "notams" in flight_plan_data:
            notams = flight_plan_data["notams"]
            if isinstance(notams, list):
                notam_text = "\n".join(notams[:3])  # Show first 3 NOTAMs
                if len(notams) > 3:
                    notam_text += f"\n... and {len(notams) - 3} more"
                
                embed.add_field(
                    name=f"{self.emojis['warning']} NOTAMs",
                    value=notam_text,
                    inline=False
                )
        
        embed.set_footer(text="Flight planning data • Always verify with current sources")
        
        return embed
    
    def create_error_embed(self, title: str, description: str) -> discord.Embed:
        """Create user-friendly error embeds with solutions"""
        embed = discord.Embed(
            title=f"{self.emojis['danger']} {title}",
            description=description,
            color=self.colors["danger"],
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="💡 What you can do:",
            value="• Try rephrasing your question\n• Check spelling of airport codes or aircraft names\n• Ask for help with `!help`",
            inline=False
        )
        
        embed.set_footer(text="If this error persists, please report it to the administrators")
        
        return embed
    
    def create_info_embed(self, title: str, description: str) -> discord.Embed:
        """Create informational embeds for general information"""
        embed = discord.Embed(
            title=f"{self.emojis['info']} {title}",
            description=description,
            color=self.colors["info"],
            timestamp=datetime.utcnow()
        )
        
        return embed
    
    def create_response_embed(self, response: str, author: discord.User) -> discord.Embed:
        """
        Create general response embed for AI responses
        Used when response contains structured data indicators
        """
        # Detect response type and choose appropriate formatting
        response_lower = response.lower()
        
        if any(indicator in response_lower for indicator in ["metar:", "taf:", "weather:"]):
            # Weather-related response
            embed = discord.Embed(
                title=f"{self.emojis['weather']} Aviation Weather Information",
                description=response,
                color=self.colors["weather_vfr"],
                timestamp=datetime.utcnow()
            )
        elif any(indicator in response_lower for indicator in ["aircraft:", "plane:", "helicopter:"]):
            # Aircraft-related response
            embed = discord.Embed(
                title=f"{self.emojis['aircraft']} Aircraft Information",
                description=response,
                color=self.colors["aircraft"],
                timestamp=datetime.utcnow()
            )
        elif any(indicator in response_lower for indicator in ["regulation:", "far:", "rule:"]):
            # Regulation-related response
            embed = discord.Embed(
                title=f"{self.emojis['regulation']} Aviation Regulations",
                description=response,
                color=self.colors["regulation"],
                timestamp=datetime.utcnow()
            )
        elif any(indicator in response_lower for indicator in ["flight plan:", "navigation:", "route:"]):
            # Flight planning response
            embed = discord.Embed(
                title=f"{self.emojis['navigation']} Flight Planning",
                description=response,
                color=self.colors["primary"],
                timestamp=datetime.utcnow()
            )
        else:
            # General aviation response
            embed = discord.Embed(
                title=f"{self.emojis['aircraft']} Aviation Information",
                description=response,
                color=self.colors["primary"],
                timestamp=datetime.utcnow()
            )
        
        # Truncate long descriptions
        if len(embed.description) > 2000:
            embed.description = embed.description[:1900] + "..."
            embed.add_field(
                name="📝 Note",
                value="Response was truncated due to length. Ask for specific details if needed.",
                inline=False
            )
        
        embed.set_footer(
            text=f"Requested by {author.display_name}",
            icon_url=author.avatar.url if author.avatar else None
        )
        
        return embed
    
    def create_success_embed(self, title: str, description: str) -> discord.Embed:
        """Create success confirmation embeds"""
        embed = discord.Embed(
            title=f"{self.emojis['success']} {title}",
            description=description,
            color=self.colors["success"],
            timestamp=datetime.utcnow()
        )
        
        return embed
    
    def create_warning_embed(self, title: str, description: str) -> discord.Embed:
        """Create warning embeds for important notices"""
        embed = discord.Embed(
            title=f"{self.emojis['warning']} {title}",
            description=description,
            color=self.colors["warning"],
            timestamp=datetime.utcnow()
        )
        
        return embed