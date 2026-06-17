"""
V4 Aviation Data Sources Integration
External API connections for real-time aviation data
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import os
import hashlib
from dataclasses import dataclass, asdict
import time
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

@dataclass
class APIEndpoint:
    """API endpoint configuration"""
    name: str
    base_url: str
    api_key_env: Optional[str]  # Environment variable name for API key
    rate_limit: int  # Requests per minute
    timeout: int  # Request timeout in seconds
    cache_duration: int  # Cache duration in seconds
    is_active: bool = True

@dataclass
class CacheEntry:
    """Cache entry for API responses"""
    data: Any
    timestamp: datetime
    expires_at: datetime
    cache_key: str

class RateLimiter:
    """Rate limiter for API requests"""
    
    def __init__(self, max_requests: int, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make a request"""
        async with self.lock:
            now = time.time()
            
            # Remove old requests outside time window
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            
            # Check if we can make a request
            if len(self.requests) >= self.max_requests:
                # Calculate wait time
                oldest_request = min(self.requests)
                wait_time = self.time_window - (now - oldest_request)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    return await self.acquire()  # Recursive call after waiting
            
            # Record this request
            self.requests.append(now)
            return True

class AviationDataManager:
    """
    Manages external aviation data sources with caching and rate limiting
    Integrates with FAA APIs, weather services, and flight tracking
    """
    
    def __init__(self, cache_dir: str = "data/api_cache"):
        self.cache_dir = cache_dir
        self.cache: Dict[str, CacheEntry] = {}
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        
        # API endpoint configurations
        self.endpoints = self._initialize_endpoints()
        
        # Initialize rate limiters
        for endpoint in self.endpoints.values():
            self.rate_limiters[endpoint.name] = RateLimiter(endpoint.rate_limit)
        
        # Ensure cache directory exists
        os.makedirs(cache_dir, exist_ok=True)
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)
    
    def _initialize_endpoints(self) -> Dict[str, APIEndpoint]:
        """Initialize API endpoint configurations"""
        return {
            "aviationweather": APIEndpoint(
                name="aviationweather",
                base_url="https://aviationweather.gov/api/data",
                api_key_env=None,  # No API key required
                rate_limit=60,  # 60 requests per minute
                timeout=10,
                cache_duration=300  # 5 minutes
            ),
            "faa_notam": APIEndpoint(
                name="faa_notam",
                base_url="https://external-api.faa.gov/notamSearch/search",
                api_key_env="FAA_API_KEY",
                rate_limit=30,
                timeout=15,
                cache_duration=600  # 10 minutes
            ),
            "flightaware": APIEndpoint(
                name="flightaware",
                base_url="https://aeroapi.flightaware.com/aeroapi",
                api_key_env="FLIGHTAWARE_API_KEY",
                rate_limit=20,
                timeout=10,
                cache_duration=180  # 3 minutes
            ),
            "opensky": APIEndpoint(
                name="opensky",
                base_url="https://opensky-network.org/api",
                api_key_env=None,  # Optional API key
                rate_limit=10,  # Conservative limit for free tier
                timeout=10,
                cache_duration=60  # 1 minute
            )
        }
    
    async def initialize(self):
        """Initialize the aviation data manager"""
        self.logger.info("Initializing aviation data manager...")
        
        # Create HTTP session
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
        # Load cache from disk
        await self._load_cache()
        
        self.logger.info("Aviation data manager initialized")
    
    async def shutdown(self):
        """Shutdown the aviation data manager"""
        if self.session:
            await self.session.close()
        
        # Save cache to disk
        await self._save_cache()
        
        self.logger.info("Aviation data manager shutdown complete")
    
    async def _load_cache(self):
        """Load cache from disk"""
        cache_file = os.path.join(self.cache_dir, "api_cache.json")
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                for key, entry_data in cache_data.items():
                    expires_at = datetime.fromisoformat(entry_data['expires_at'])
                    
                    # Only load non-expired entries
                    if expires_at > datetime.utcnow():
                        self.cache[key] = CacheEntry(
                            data=entry_data['data'],
                            timestamp=datetime.fromisoformat(entry_data['timestamp']),
                            expires_at=expires_at,
                            cache_key=key
                        )
                
                self.logger.info(f"Loaded {len(self.cache)} cached entries")
                
            except Exception as e:
                self.logger.error(f"Error loading cache: {e}")
    
    async def _save_cache(self):
        """Save cache to disk"""
        cache_file = os.path.join(self.cache_dir, "api_cache.json")
        
        try:
            # Convert cache to serializable format
            cache_data = {}
            for key, entry in self.cache.items():
                if entry.expires_at > datetime.utcnow():  # Only save non-expired
                    cache_data[key] = {
                        'data': entry.data,
                        'timestamp': entry.timestamp.isoformat(),
                        'expires_at': entry.expires_at.isoformat()
                    }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved {len(cache_data)} cache entries")
            
        except Exception as e:
            self.logger.error(f"Error saving cache: {e}")
    
    def _generate_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate cache key for request"""
        key_data = f"{endpoint}_{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()
    
    async def _get_cached_data(self, cache_key: str) -> Optional[Any]:
        """Get data from cache if available and not expired"""
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if entry.expires_at > datetime.utcnow():
                return entry.data
            else:
                # Remove expired entry
                del self.cache[cache_key]
        
        return None
    
    async def _cache_data(self, cache_key: str, data: Any, cache_duration: int):
        """Cache data with expiration"""
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=cache_duration)
        
        self.cache[cache_key] = CacheEntry(
            data=data,
            timestamp=now,
            expires_at=expires_at,
            cache_key=cache_key
        )
    
    async def _make_request(self, endpoint: APIEndpoint, url: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request with rate limiting and error handling"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        # Apply rate limiting
        await self.rate_limiters[endpoint.name].acquire()
        
        # Prepare headers
        headers = {
            'User-Agent': 'AviationGirl-Bot/4.0',
            'Accept': 'application/json'
        }
        
        # Add API key if required
        if endpoint.api_key_env:
            api_key = os.getenv(endpoint.api_key_env)
            if api_key:
                if endpoint.name == "flightaware":
                    headers['x-apikey'] = api_key
                elif endpoint.name == "faa_notam":
                    headers['client_id'] = api_key
                # Add other API key formats as needed
        
        try:
            async with self.session.get(url, params=params, headers=headers, 
                                      timeout=aiohttp.ClientTimeout(total=endpoint.timeout)) as response:
                
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    
                    if 'application/json' in content_type:
                        return await response.json()
                    elif 'application/xml' in content_type or 'text/xml' in content_type:
                        text = await response.text()
                        return self._parse_xml_response(text)
                    else:
                        text = await response.text()
                        return {'raw_data': text, 'content_type': content_type}
                
                elif response.status == 429:  # Rate limited
                    self.logger.warning(f"Rate limited by {endpoint.name}")
                    await asyncio.sleep(60)  # Wait 1 minute
                    return await self._make_request(endpoint, url, params)  # Retry
                
                else:
                    error_text = await response.text()
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"HTTP {response.status}: {error_text}"
                    )
        
        except asyncio.TimeoutError:
            raise TimeoutError(f"Request to {endpoint.name} timed out")
        except Exception as e:
            self.logger.error(f"Request to {endpoint.name} failed: {e}")
            raise
    
    def _parse_xml_response(self, xml_text: str) -> Dict[str, Any]:
        """Parse XML response to dictionary"""
        try:
            root = ET.fromstring(xml_text)
            return self._xml_to_dict(root)
        except ET.ParseError as e:
            self.logger.error(f"XML parsing error: {e}")
            return {'raw_xml': xml_text, 'parse_error': str(e)}
    
    def _xml_to_dict(self, element) -> Dict[str, Any]:
        """Convert XML element to dictionary"""
        result = {}
        
        # Add attributes
        if element.attrib:
            result['@attributes'] = element.attrib
        
        # Add text content
        if element.text and element.text.strip():
            if len(element) == 0:  # Leaf node
                return element.text.strip()
            else:
                result['text'] = element.text.strip()
        
        # Add child elements
        for child in element:
            child_data = self._xml_to_dict(child)
            
            if child.tag in result:
                # Multiple children with same tag - convert to list
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        
        return result
    
    async def get_weather(self, airport_code: str) -> Dict[str, Any]:
        """
        Get current weather information for an airport
        Returns METAR and TAF data
        """
        endpoint = self.endpoints["aviationweather"]
        cache_key = self._generate_cache_key("weather", {"airport": airport_code})
        
        # Check cache first
        cached_data = await self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        try:
            # Get METAR data
            metar_url = f"{endpoint.base_url}/metar"
            metar_params = {
                'ids': airport_code.upper(),
                'format': 'json',
                'taf': 'false',
                'hours': '3'
            }
            
            metar_data = await self._make_request(endpoint, metar_url, metar_params)
            
            # Get TAF data
            taf_url = f"{endpoint.base_url}/taf"
            taf_params = {
                'ids': airport_code.upper(),
                'format': 'json',
                'hours': '12'
            }
            
            taf_data = await self._make_request(endpoint, taf_url, taf_params)
            
            # Combine and format data
            weather_data = {
                'airport_code': airport_code.upper(),
                'timestamp': datetime.utcnow().isoformat(),
                'metar': self._process_metar_data(metar_data),
                'taf': self._process_taf_data(taf_data),
                'source': 'aviationweather.gov'
            }
            
            # Cache the result
            await self._cache_data(cache_key, weather_data, endpoint.cache_duration)
            
            return weather_data
            
        except Exception as e:
            self.logger.error(f"Error getting weather for {airport_code}: {e}")
            return {
                'airport_code': airport_code.upper(),
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'metar': None,
                'taf': None
            }
    
    def _process_metar_data(self, metar_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process METAR data from API response"""
        if not metar_data or not isinstance(metar_data, list) or len(metar_data) == 0:
            return None
        
        # Get the most recent METAR
        latest_metar = metar_data[0]
        
        return {
            'raw': latest_metar.get('rawOb', ''),
            'observation_time': latest_metar.get('obsTime', ''),
            'flight_category': latest_metar.get('fltCat', ''),
            'visibility': latest_metar.get('visib', ''),
            'wind_direction': latest_metar.get('wdir', ''),
            'wind_speed': latest_metar.get('wspd', ''),
            'wind_gust': latest_metar.get('wgst', ''),
            'temperature': latest_metar.get('temp', ''),
            'dewpoint': latest_metar.get('dewp', ''),
            'altimeter': latest_metar.get('altim', ''),
            'clouds': latest_metar.get('clds', []),
            'weather': latest_metar.get('wx', [])
        }
    
    def _process_taf_data(self, taf_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process TAF data from API response"""
        if not taf_data or not isinstance(taf_data, list) or len(taf_data) == 0:
            return None
        
        # Get the most recent TAF
        latest_taf = taf_data[0]
        
        return {
            'raw': latest_taf.get('rawTAF', ''),
            'issue_time': latest_taf.get('issTime', ''),
            'valid_time': latest_taf.get('validTime', ''),
            'forecasts': latest_taf.get('fcsts', [])
        }
    
    async def get_flight_info(self, flight_number: str) -> Dict[str, Any]:
        """
        Get flight tracking information
        Uses OpenSky Network API (free tier)
        """
        endpoint = self.endpoints["opensky"]
        cache_key = self._generate_cache_key("flight", {"flight": flight_number})
        
        # Check cache first
        cached_data = await self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        try:
            # OpenSky API endpoint for flight information
            url = f"{endpoint.base_url}/flights/all"
            params = {
                'begin': int((datetime.utcnow() - timedelta(hours=24)).timestamp()),
                'end': int(datetime.utcnow().timestamp())
            }
            
            flight_data = await self._make_request(endpoint, url, params)
            
            # Filter for specific flight
            matching_flights = []
            if isinstance(flight_data, list):
                for flight in flight_data:
                    if (flight.get('callsign', '').strip().upper() == flight_number.upper() or
                        flight_number.upper() in flight.get('callsign', '').strip().upper()):
                        matching_flights.append(flight)
            
            result = {
                'flight_number': flight_number.upper(),
                'timestamp': datetime.utcnow().isoformat(),
                'flights': matching_flights,
                'source': 'opensky-network.org'
            }
            
            # Cache the result
            await self._cache_data(cache_key, result, endpoint.cache_duration)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting flight info for {flight_number}: {e}")
            return {
                'flight_number': flight_number.upper(),
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'flights': []
            }
    
    async def get_notams(self, airport_code: str) -> List[Dict[str, Any]]:
        """
        Get NOTAMs for an airport
        Note: FAA NOTAM API requires registration and API key
        """
        endpoint = self.endpoints["faa_notam"]
        cache_key = self._generate_cache_key("notams", {"airport": airport_code})
        
        # Check cache first
        cached_data = await self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        # Check if API key is available
        api_key = os.getenv(endpoint.api_key_env)
        if not api_key:
            self.logger.warning("FAA NOTAM API key not available")
            return [{
                'airport_code': airport_code.upper(),
                'timestamp': datetime.utcnow().isoformat(),
                'error': 'API key not configured',
                'notams': []
            }]
        
        try:
            params = {
                'searchType': 'LOCATION',
                'locationIdentifiers': airport_code.upper(),
                'sortBy': 'issueDate',
                'sortOrder': 'DESC'
            }
            
            notam_data = await self._make_request(endpoint, endpoint.base_url, params)
            
            # Process NOTAM data
            notams = []
            if isinstance(notam_data, dict) and 'notamList' in notam_data:
                for notam in notam_data['notamList']:
                    notams.append({
                        'id': notam.get('notamId', ''),
                        'issue_date': notam.get('issueDate', ''),
                        'start_date': notam.get('startDate', ''),
                        'end_date': notam.get('endDate', ''),
                        'text': notam.get('text', ''),
                        'location': notam.get('location', ''),
                        'type': notam.get('type', '')
                    })
            
            result = {
                'airport_code': airport_code.upper(),
                'timestamp': datetime.utcnow().isoformat(),
                'notams': notams,
                'source': 'faa.gov'
            }
            
            # Cache the result
            await self._cache_data(cache_key, result, endpoint.cache_duration)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting NOTAMs for {airport_code}: {e}")
            return [{
                'airport_code': airport_code.upper(),
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'notams': []
            }]
    
    async def search_regulations(self, query: str) -> List[Dict[str, Any]]:
        """
        Search aviation regulations
        This is a placeholder - would integrate with FAA regulation database
        """
        # This would integrate with FAA's regulation API or database
        # For now, return a placeholder response
        
        return [{
            'query': query,
            'timestamp': datetime.utcnow().isoformat(),
            'regulations': [],
            'source': 'placeholder',
            'note': 'Regulation search not yet implemented - would integrate with FAA database'
        }]
    
    async def get_airport_info(self, airport_code: str) -> Dict[str, Any]:
        """
        Get airport information
        This would integrate with airport database APIs
        """
        # Placeholder for airport information
        # Would integrate with FAA airport database or other sources
        
        return {
            'airport_code': airport_code.upper(),
            'timestamp': datetime.utcnow().isoformat(),
            'info': {},
            'source': 'placeholder',
            'note': 'Airport info not yet implemented - would integrate with airport database'
        }
    
    def get_api_status(self) -> Dict[str, Any]:
        """Get status of all API endpoints"""
        status = {
            'timestamp': datetime.utcnow().isoformat(),
            'endpoints': {},
            'cache_stats': {
                'total_entries': len(self.cache),
                'cache_directory': self.cache_dir
            }
        }
        
        for name, endpoint in self.endpoints.items():
            api_key_configured = True
            if endpoint.api_key_env:
                api_key_configured = bool(os.getenv(endpoint.api_key_env))
            
            status['endpoints'][name] = {
                'base_url': endpoint.base_url,
                'is_active': endpoint.is_active,
                'rate_limit': endpoint.rate_limit,
                'api_key_configured': api_key_configured,
                'cache_duration': endpoint.cache_duration
            }
        
        return status
    
    async def clear_cache(self, endpoint_name: Optional[str] = None):
        """Clear cache for specific endpoint or all endpoints"""
        if endpoint_name:
            # Clear cache for specific endpoint
            keys_to_remove = [key for key in self.cache.keys() 
                            if key.startswith(endpoint_name)]
            for key in keys_to_remove:
                del self.cache[key]
            
            self.logger.info(f"Cleared {len(keys_to_remove)} cache entries for {endpoint_name}")
        else:
            # Clear all cache
            cache_count = len(self.cache)
            self.cache.clear()
            self.logger.info(f"Cleared all {cache_count} cache entries")
        
        # Save updated cache
        await self._save_cache()
    
    async def _make_api_request(self, endpoint: APIEndpoint, url: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Alias for _make_request method for test compatibility"""
        return await self._make_request(endpoint, url, params)