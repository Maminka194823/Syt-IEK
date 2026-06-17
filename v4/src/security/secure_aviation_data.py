"""
V4 Secure Aviation Data Manager
Secure integration with external aviation APIs using API Security Manager
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import hashlib
from dataclasses import dataclass
from .api_security_manager import APISecurityManager
from .credential_manager import CredentialManager
from .encryption_manager import EncryptionManager

@dataclass
class SecureAPIResponse:
    """Secure API response with validation"""
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    timestamp: datetime
    source: str
    cached: bool = False
    security_validated: bool = False

class SecureAviationDataManager:
    """
    Secure aviation data manager with encrypted caching and secure API access
    Integrates with API Security Manager for all external connections
    """
    
    def __init__(
        self, 
        encryption_manager: EncryptionManager,
        credential_manager: CredentialManager,
        cache_dir: str = "data/secure_cache"
    ):
        """
        Initialize secure aviation data manager
        
        Args:
            encryption_manager: Encryption manager for secure caching
            credential_manager: Credential manager for API keys
            cache_dir: Directory for encrypted cache storage
        """
        self.encryption_manager = encryption_manager
        self.credential_manager = credential_manager
        self.cache_dir = cache_dir
        
        # Initialize API security manager
        self.api_security = APISecurityManager(credential_manager)
        
        # Cache settings
        self.cache_durations = {
            "weather": 300,      # 5 minutes
            "notam": 900,        # 15 minutes
            "flight_tracking": 60,  # 1 minute
            "airport_info": 3600,   # 1 hour
            "aircraft_info": 86400  # 24 hours
        }
        
        # Data validation patterns
        self.validation_patterns = {
            "metar": {
                "required_fields": ["station_id", "observation_time", "raw_text"],
                "format_pattern": r"^[A-Z]{4}\s+\d{6}Z"
            },
            "taf": {
                "required_fields": ["station_id", "issue_time", "raw_text"],
                "format_pattern": r"^TAF\s+[A-Z]{4}"
            },
            "notam": {
                "required_fields": ["notam_id", "location", "effective_start"],
                "format_pattern": r"^[A-Z]\d{4}/\d{2}"
            },
            "flight": {
                "required_fields": ["flight_id", "aircraft_type"],
                "format_pattern": r"^[A-Z]{2,3}\d{1,4}[A-Z]?$"
            }
        }
        
        # Security monitoring
        self.security_stats = {
            "total_requests": 0,
            "cached_responses": 0,
            "validation_failures": 0,
            "security_violations": 0,
            "successful_retrievals": 0
        }
        
        # Ensure cache directory exists
        import os
        os.makedirs(cache_dir, exist_ok=True)
    
    async def get_weather_data(
        self, 
        airport_code: str, 
        data_type: str = "metar"
    ) -> SecureAPIResponse:
        """
        Get weather data with security validation
        
        Args:
            airport_code: ICAO airport code
            data_type: Type of weather data (metar, taf)
            
        Returns:
            SecureAPIResponse with weather data
        """
        try:
            self.security_stats["total_requests"] += 1
            
            # Validate input
            if not self._validate_airport_code(airport_code):
                return SecureAPIResponse(
                    success=False,
                    data=None,
                    error="Invalid airport code format",
                    timestamp=datetime.utcnow(),
                    source="validation",
                    security_validated=False
                )
            
            # Check cache first
            cache_key = f"weather_{data_type}_{airport_code}"
            cached_response = await self._get_cached_data(cache_key, "weather")
            
            if cached_response:
                self.security_stats["cached_responses"] += 1
                return SecureAPIResponse(
                    success=True,
                    data=cached_response,
                    error=None,
                    timestamp=datetime.utcnow(),
                    source="aviationweather",
                    cached=True,
                    security_validated=True
                )
            
            # Make secure API request
            endpoint = f"metar" if data_type == "metar" else f"taf"
            params = {
                "ids": airport_code,
                "format": "json",
                "taf": "false" if data_type == "metar" else "true"
            }
            
            success, response_data, error = await self.api_security.make_secure_request(
                api_name="aviationweather",
                endpoint=endpoint,
                method="GET",
                params=params
            )
            
            if not success:
                return SecureAPIResponse(
                    success=False,
                    data=None,
                    error=error,
                    timestamp=datetime.utcnow(),
                    source="aviationweather",
                    security_validated=False
                )
            
            # Validate response data
            validated_data = await self._validate_weather_data(response_data, data_type)
            
            if not validated_data:
                self.security_stats["validation_failures"] += 1
                return SecureAPIResponse(
                    success=False,
                    data=None,
                    error="Weather data validation failed",
                    timestamp=datetime.utcnow(),
                    source="aviationweather",
                    security_validated=False
                )
            
            # Cache the validated data
            await self._cache_data(cache_key, validated_data, "weather")
            
            self.security_stats["successful_retrievals"] += 1
            
            return SecureAPIResponse(
                success=True,
                data=validated_data,
                error=None,
                timestamp=datetime.utcnow(),
                source="aviationweather",
                cached=False,
                security_validated=True
            )
            
        except Exception as e:
            logging.error(f"Error getting weather data for {airport_code}: {e}")
            return SecureAPIResponse(
                success=False,
                data=None,
                error=str(e),
                timestamp=datetime.utcnow(),
                source="error",
                security_validated=False
            )
    
    async def get_notam_data(self, airport_code: str) -> SecureAPIResponse:
        """
        Get NOTAM data with security validation
        
        Args:
            airport_code: ICAO airport code
            
        Returns:
            SecureAPIResponse with NOTAM data
        """
        try:
            self.security_stats["total_requests"] += 1
            
            # Validate input
            if not self._validate_airport_code(airport_code):
                return SecureAPIResponse(
                    success=False,
                    data=None,
                    error="Invalid airport code format",
                    timestamp=datetime.utcnow(),
                    source="validation",
                    security_validated=False
                )
            
            # Check cache
            cache_key = f"notam_{airport_code}"
            cached_response = await self._get_cached_data(cache_key, "notam")
            
            if cached_response:
                self.security_stats["cached_responses"] += 1
                return SecureAPIResponse(
                    success=True,
                    data=cached_response,
                    error=None,
                    timestamp=datetime.utcnow(),
                    source="faa_notam",
                    cached=True,
                    security_validated=True
                )
            
            # Make secure API request
            endpoint = f"notams/search"
            params = {
                "locationIdentifiers": airport_code,
                "maxItems": 50
            }
            
            success, response_data, error = await self.api_security.make_secure_request(
                api_name="faa_notam",
                endpoint=endpoint,
                method="GET",
                params=params
            )
            
            if not success:
                return SecureAPIResponse(
                    success=False,
                    data=None,
                    error=error,
                    timestamp=datetime.utcnow(),
                    source="faa_notam",
                    security_validated=False
                )
            
            # Validate response data
            validated_data = await self._validate_notam_data(response_data)
            
            if not validated_data:
                self.security_stats["validation_failures"] += 1
                return SecureAPIResponse(
                    success=False,
                    data=None,
                    error="NOTAM data validation failed",
                    timestamp=datetime.utcnow(),
                    source="faa_notam",
                    security_validated=False
                )
            
            # Cache the validated data
            await self._cache_data(cache_key, validated_data, "notam")
            
            self.security_stats["successful_retrievals"] += 1
            
            return SecureAPIResponse(
                success=True,
                data=validated_data,
                error=None,
                timestamp=datetime.utcnow(),
                source="faa_notam",
                cached=False,
                security_validated=True
            )
            
        except Exception as e:
            logging.error(f"Error getting NOTAM data for {airport_code}: {e}")
            return SecureAPIResponse(
                success=False,
                data=None,
                error=str(e),
                timestamp=datetime.utcnow(),
                source="error",
                security_validated=False
            )
    
    async def get_flight_data(self, flight_number: str) -> SecureAPIResponse:
        """
        Get flight tracking data with security validation
        
        Args:
            flight_number: Flight number (e.g., "UAL123")
            
        Returns:
            SecureAPIResponse with flight data
        """
        try:
            self.security_stats["total_requests"] += 1
            
            # Validate input
            if not self._validate_flight_number(flight_number):
                return SecureAPIResponse(
                    success=False,
                    data=None,
                    error="Invalid flight number format",
                    timestamp=datetime.utcnow(),
                    source="validation",
                    security_validated=False
                )
            
            # Check cache
            cache_key = f"flight_{flight_number}"
            cached_response = await self._get_cached_data(cache_key, "flight_tracking")
            
            if cached_response:
                self.security_stats["cached_responses"] += 1
                return SecureAPIResponse(
                    success=True,
                    data=cached_response,
                    error=None,
                    timestamp=datetime.utcnow(),
                    source="flightaware",
                    cached=True,
                    security_validated=True
                )
            
            # Make secure API request
            endpoint = f"flights/{flight_number}"
            
            success, response_data, error = await self.api_security.make_secure_request(
                api_name="flightaware",
                endpoint=endpoint,
                method="GET"
            )
            
            if not success:
                return SecureAPIResponse(
                    success=False,
                    data=None,
                    error=error,
                    timestamp=datetime.utcnow(),
                    source="flightaware",
                    security_validated=False
                )
            
            # Validate response data
            validated_data = await self._validate_flight_data(response_data)
            
            if not validated_data:
                self.security_stats["validation_failures"] += 1
                return SecureAPIResponse(
                    success=False,
                    data=None,
                    error="Flight data validation failed",
                    timestamp=datetime.utcnow(),
                    source="flightaware",
                    security_validated=False
                )
            
            # Cache the validated data
            await self._cache_data(cache_key, validated_data, "flight_tracking")
            
            self.security_stats["successful_retrievals"] += 1
            
            return SecureAPIResponse(
                success=True,
                data=validated_data,
                error=None,
                timestamp=datetime.utcnow(),
                source="flightaware",
                cached=False,
                security_validated=True
            )
            
        except Exception as e:
            logging.error(f"Error getting flight data for {flight_number}: {e}")
            return SecureAPIResponse(
                success=False,
                data=None,
                error=str(e),
                timestamp=datetime.utcnow(),
                source="error",
                security_validated=False
            )
    
    def _validate_airport_code(self, airport_code: str) -> bool:
        """Validate airport code format"""
        if not airport_code or len(airport_code) != 4:
            return False
        
        # ICAO codes are 4 letters
        if not airport_code.isalpha():
            return False
        
        return airport_code.isupper()
    
    def _validate_flight_number(self, flight_number: str) -> bool:
        """Validate flight number format"""
        if not flight_number or len(flight_number) < 3 or len(flight_number) > 8:
            return False
        
        # Basic pattern: 2-3 letters followed by 1-4 digits, optional letter
        import re
        pattern = r"^[A-Z]{2,3}\d{1,4}[A-Z]?$"
        return bool(re.match(pattern, flight_number.upper()))
    
    async def _validate_weather_data(self, data: Dict[str, Any], data_type: str) -> Optional[Dict[str, Any]]:
        """Validate weather data structure and content"""
        try:
            if not data or not isinstance(data, dict):
                return None
            
            validation_config = self.validation_patterns.get(data_type)
            if not validation_config:
                return None
            
            # Check for required fields
            required_fields = validation_config["required_fields"]
            
            # Handle different response structures
            if data_type == "metar" and "features" in data:
                # GeoJSON format
                features = data.get("features", [])
                if not features:
                    return None
                
                validated_features = []
                for feature in features:
                    properties = feature.get("properties", {})
                    
                    # Check required fields
                    if all(field in properties for field in required_fields):
                        # Validate format
                        raw_text = properties.get("raw_text", "")
                        if raw_text and self._validate_metar_format(raw_text):
                            validated_features.append(feature)
                
                if validated_features:
                    return {"features": validated_features, "type": "FeatureCollection"}
            
            elif data_type == "taf" and "features" in data:
                # Similar validation for TAF
                features = data.get("features", [])
                if not features:
                    return None
                
                validated_features = []
                for feature in features:
                    properties = feature.get("properties", {})
                    
                    if all(field in properties for field in required_fields):
                        raw_text = properties.get("raw_text", "")
                        if raw_text and raw_text.startswith("TAF"):
                            validated_features.append(feature)
                
                if validated_features:
                    return {"features": validated_features, "type": "FeatureCollection"}
            
            return None
            
        except Exception as e:
            logging.error(f"Error validating weather data: {e}")
            return None
    
    def _validate_metar_format(self, metar_text: str) -> bool:
        """Validate METAR format"""
        try:
            # Basic METAR validation
            parts = metar_text.split()
            if len(parts) < 3:
                return False
            
            # First part should be airport code
            if len(parts[0]) != 4 or not parts[0].isalpha():
                return False
            
            # Second part should be timestamp
            if len(parts[1]) != 7 or not parts[1].endswith('Z'):
                return False
            
            return True
            
        except Exception:
            return False
    
    async def _validate_notam_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate NOTAM data structure and content"""
        try:
            if not data or not isinstance(data, dict):
                return None
            
            # Check for NOTAM items
            items = data.get("items", [])
            if not items:
                return None
            
            validated_items = []
            for item in items:
                # Check required fields
                if all(field in item for field in ["notamNumber", "location", "effectiveStart"]):
                    # Basic format validation
                    notam_number = item.get("notamNumber", "")
                    if notam_number and len(notam_number) >= 6:
                        validated_items.append(item)
            
            if validated_items:
                return {"items": validated_items, "count": len(validated_items)}
            
            return None
            
        except Exception as e:
            logging.error(f"Error validating NOTAM data: {e}")
            return None
    
    async def _validate_flight_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate flight data structure and content"""
        try:
            if not data or not isinstance(data, dict):
                return None
            
            # Check for flight information
            if "flights" in data:
                flights = data["flights"]
                if not flights:
                    return None
                
                validated_flights = []
                for flight in flights:
                    # Check required fields
                    if "ident" in flight and "aircraft_type" in flight:
                        validated_flights.append(flight)
                
                if validated_flights:
                    return {"flights": validated_flights}
            
            elif "ident" in data and "aircraft_type" in data:
                # Single flight response
                return data
            
            return None
            
        except Exception as e:
            logging.error(f"Error validating flight data: {e}")
            return None
    
    async def _get_cached_data(self, cache_key: str, data_type: str) -> Optional[Dict[str, Any]]:
        """Get data from encrypted cache"""
        try:
            cache_file = f"{self.cache_dir}/{hashlib.md5(cache_key.encode()).hexdigest()}.cache"
            
            if not os.path.exists(cache_file):
                return None
            
            # Read encrypted cache file
            with open(cache_file, 'r', encoding='utf-8') as f:
                encrypted_data = f.read()
            
            # Decrypt cache data
            cache_entry = self.encryption_manager.decrypt_data(encrypted_data, return_dict=True)
            
            # Check expiration
            expires_at = datetime.fromisoformat(cache_entry["expires_at"])
            if datetime.utcnow() > expires_at:
                # Remove expired cache
                os.remove(cache_file)
                return None
            
            return cache_entry["data"]
            
        except Exception as e:
            logging.error(f"Error reading cache for {cache_key}: {e}")
            return None
    
    async def _cache_data(self, cache_key: str, data: Dict[str, Any], data_type: str):
        """Store data in encrypted cache"""
        try:
            cache_duration = self.cache_durations.get(data_type, 300)
            expires_at = datetime.utcnow() + timedelta(seconds=cache_duration)
            
            cache_entry = {
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
                "expires_at": expires_at.isoformat(),
                "cache_key": cache_key,
                "data_type": data_type
            }
            
            # Encrypt cache entry
            encrypted_data = self.encryption_manager.encrypt_data(cache_entry)
            
            # Save to cache file
            cache_file = f"{self.cache_dir}/{hashlib.md5(cache_key.encode()).hexdigest()}.cache"
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(encrypted_data)
                
        except Exception as e:
            logging.error(f"Error caching data for {cache_key}: {e}")
    
    async def validate_all_connections(self) -> Dict[str, Any]:
        """Validate all API connections"""
        return await self.api_security.validate_api_connections()
    
    async def rotate_api_credentials(self, api_name: str, new_credential: str) -> bool:
        """Rotate API credentials"""
        return await self.api_security.rotate_api_credentials(api_name, new_credential)
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Get comprehensive security statistics"""
        api_stats = self.api_security.get_security_stats()
        
        return {
            "aviation_data_stats": self.security_stats.copy(),
            "api_security_stats": api_stats,
            "cache_info": {
                "cache_directory": self.cache_dir,
                "cache_durations": self.cache_durations
            }
        }
    
    async def clear_cache(self, data_type: Optional[str] = None) -> int:
        """Clear cached data"""
        try:
            import os
            import glob
            
            if data_type:
                # Clear specific data type (would need more sophisticated cache key tracking)
                pattern = f"{self.cache_dir}/*.cache"
            else:
                pattern = f"{self.cache_dir}/*.cache"
            
            cache_files = glob.glob(pattern)
            cleared_count = 0
            
            for cache_file in cache_files:
                try:
                    os.remove(cache_file)
                    cleared_count += 1
                except Exception as e:
                    logging.error(f"Error removing cache file {cache_file}: {e}")
            
            logging.info(f"Cleared {cleared_count} cache files")
            return cleared_count
            
        except Exception as e:
            logging.error(f"Error clearing cache: {e}")
            return 0