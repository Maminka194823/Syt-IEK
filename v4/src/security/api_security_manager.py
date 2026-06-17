"""
V4 API Security Manager
Handles secure external API access with authentication and monitoring
"""

import os
import ssl
import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import hashlib
import json
from urllib.parse import urlparse
import certifi
from .credential_manager import CredentialManager

class APISecurityManager:
    """
    Manages secure external API access with proper authentication,
    connection validation, and security monitoring
    """
    
    def __init__(self, credential_manager: CredentialManager):
        """
        Initialize API security manager
        
        Args:
            credential_manager: Credential manager for API keys
        """
        self.credential_manager = credential_manager
        
        # Security settings
        self.ssl_context = self._create_secure_ssl_context()
        self.timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        # API endpoint configurations
        self.api_configs = {
            "aviationweather": {
                "base_url": "https://aviationweather.gov/api/data",
                "requires_auth": False,
                "rate_limit": 60,  # requests per minute
                "ssl_verify": True,
                "allowed_methods": ["GET"],
                "security_headers": {
                    "User-Agent": "Aviation-Discord-Bot/1.0"
                }
            },
            "faa_notam": {
                "base_url": "https://external-api.faa.gov/notamapi/v1",
                "requires_auth": True,
                "auth_type": "api_key",
                "rate_limit": 100,
                "ssl_verify": True,
                "allowed_methods": ["GET"],
                "security_headers": {
                    "User-Agent": "Aviation-Discord-Bot/1.0",
                    "Accept": "application/json"
                }
            },
            "flightaware": {
                "base_url": "https://aeroapi.flightaware.com/aeroapi",
                "requires_auth": True,
                "auth_type": "api_key",
                "rate_limit": 500,
                "ssl_verify": True,
                "allowed_methods": ["GET"],
                "security_headers": {
                    "User-Agent": "Aviation-Discord-Bot/1.0",
                    "Accept": "application/json"
                }
            },
            "opensky": {
                "base_url": "https://opensky-network.org/api",
                "requires_auth": False,
                "rate_limit": 400,  # per day for anonymous
                "ssl_verify": True,
                "allowed_methods": ["GET"],
                "security_headers": {
                    "User-Agent": "Aviation-Discord-Bot/1.0"
                }
            }
        }
        
        # Connection monitoring
        self.connection_stats = {}
        self.security_events = []
        self.failed_connections = {}
        
        # Rate limiting tracking
        self.rate_limits = {}
        
        # Security monitoring
        self.security_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "security_violations": 0,
            "ssl_errors": 0,
            "auth_failures": 0,
            "rate_limit_hits": 0
        }
    
    def _create_secure_ssl_context(self) -> ssl.SSLContext:
        """Create secure SSL context for HTTPS connections"""
        try:
            # Create SSL context with strong security settings
            context = ssl.create_default_context(cafile=certifi.where())
            
            # Set minimum TLS version
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            
            # Disable weak ciphers
            context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
            
            # Enable certificate verification
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            
            return context
            
        except Exception as e:
            logging.error(f"Error creating SSL context: {e}")
            # Fallback to default context
            return ssl.create_default_context()
    
    async def make_secure_request(
        self,
        api_name: str,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Make a secure API request with authentication and validation
        
        Args:
            api_name: Name of the API configuration
            endpoint: API endpoint path
            method: HTTP method
            params: Query parameters
            headers: Additional headers
            data: Request body data
            
        Returns:
            Tuple of (success, response_data, error_message)
        """
        try:
            # Validate API configuration
            if api_name not in self.api_configs:
                error_msg = f"Unknown API configuration: {api_name}"
                self._log_security_event("invalid_api", api_name, error_msg)
                return False, None, error_msg
            
            config = self.api_configs[api_name]
            
            # Validate method
            if method not in config["allowed_methods"]:
                error_msg = f"Method {method} not allowed for API {api_name}"
                self._log_security_event("invalid_method", api_name, error_msg)
                return False, None, error_msg
            
            # Check rate limiting
            if not await self._check_rate_limit(api_name):
                error_msg = f"Rate limit exceeded for API {api_name}"
                self.security_stats["rate_limit_hits"] += 1
                return False, None, error_msg
            
            # Build request URL
            base_url = config["base_url"]
            url = f"{base_url}/{endpoint.lstrip('/')}"
            
            # Validate URL security
            if not self._validate_url_security(url):
                error_msg = f"URL failed security validation: {url}"
                self._log_security_event("invalid_url", api_name, error_msg)
                return False, None, error_msg
            
            # Prepare headers
            request_headers = config.get("security_headers", {}).copy()
            if headers:
                request_headers.update(headers)
            
            # Add authentication if required
            if config.get("requires_auth", False):
                auth_success = await self._add_authentication(api_name, request_headers)
                if not auth_success:
                    error_msg = f"Authentication failed for API {api_name}"
                    self.security_stats["auth_failures"] += 1
                    return False, None, error_msg
            
            # Make the request
            async with aiohttp.ClientSession(
                timeout=self.timeout,
                connector=aiohttp.TCPConnector(ssl=self.ssl_context)
            ) as session:
                
                self.security_stats["total_requests"] += 1
                
                async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=request_headers,
                    json=data if data else None
                ) as response:
                    
                    # Update rate limiting
                    await self._update_rate_limit(api_name)
                    
                    # Validate response
                    if not await self._validate_response_security(response, api_name):
                        error_msg = "Response failed security validation"
                        self.security_stats["security_violations"] += 1
                        return False, None, error_msg
                    
                    # Handle response
                    if response.status == 200:
                        try:
                            response_data = await response.json()
                            self.security_stats["successful_requests"] += 1
                            self._update_connection_stats(api_name, True)
                            return True, response_data, None
                            
                        except Exception as e:
                            error_msg = f"Error parsing response: {str(e)}"
                            self.security_stats["failed_requests"] += 1
                            return False, None, error_msg
                    else:
                        error_msg = f"HTTP {response.status}: {response.reason}"
                        self.security_stats["failed_requests"] += 1
                        self._update_connection_stats(api_name, False)
                        return False, None, error_msg
        
        except ssl.SSLError as e:
            error_msg = f"SSL error: {str(e)}"
            self.security_stats["ssl_errors"] += 1
            self._log_security_event("ssl_error", api_name, error_msg)
            return False, None, error_msg
            
        except aiohttp.ClientError as e:
            error_msg = f"Client error: {str(e)}"
            self.security_stats["failed_requests"] += 1
            self._update_connection_stats(api_name, False)
            return False, None, error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.security_stats["failed_requests"] += 1
            logging.error(f"Secure request error for {api_name}: {e}")
            return False, None, error_msg
    
    def _validate_url_security(self, url: str) -> bool:
        """Validate URL for security issues"""
        try:
            parsed = urlparse(url)
            
            # Must use HTTPS
            if parsed.scheme != 'https':
                return False
            
            # Check for suspicious patterns
            suspicious_patterns = [
                'localhost', '127.0.0.1', '0.0.0.0',
                'internal', 'admin', 'test',
                '..', '//', '%2e%2e'
            ]
            
            url_lower = url.lower()
            for pattern in suspicious_patterns:
                if pattern in url_lower:
                    return False
            
            # Validate hostname
            if not parsed.hostname:
                return False
            
            # Check for private IP ranges (basic check)
            hostname = parsed.hostname.lower()
            if hostname.startswith('192.168.') or hostname.startswith('10.') or hostname.startswith('172.'):
                return False
            
            return True
            
        except Exception:
            return False
    
    async def _add_authentication(self, api_name: str, headers: Dict[str, str]) -> bool:
        """Add authentication to request headers"""
        try:
            config = self.api_configs[api_name]
            auth_type = config.get("auth_type", "api_key")
            
            if auth_type == "api_key":
                # Get API key from credential manager
                api_key = self.credential_manager.get_credential(api_name, "api_key")
                if not api_key:
                    logging.error(f"No API key found for {api_name}")
                    return False
                
                # Add API key to headers (format varies by API)
                if api_name == "faa_notam":
                    headers["client_id"] = api_key
                elif api_name == "flightaware":
                    headers["x-apikey"] = api_key
                else:
                    headers["Authorization"] = f"Bearer {api_key}"
                
                return True
            
            elif auth_type == "bearer_token":
                token = self.credential_manager.get_credential(api_name, "token")
                if not token:
                    logging.error(f"No bearer token found for {api_name}")
                    return False
                
                headers["Authorization"] = f"Bearer {token}"
                return True
            
            else:
                logging.error(f"Unsupported auth type: {auth_type}")
                return False
                
        except Exception as e:
            logging.error(f"Error adding authentication for {api_name}: {e}")
            return False
    
    async def _check_rate_limit(self, api_name: str) -> bool:
        """Check if request is within rate limits"""
        try:
            config = self.api_configs[api_name]
            rate_limit = config.get("rate_limit", 60)
            
            current_time = datetime.utcnow()
            
            if api_name not in self.rate_limits:
                self.rate_limits[api_name] = {
                    "requests": [],
                    "window_start": current_time
                }
            
            rate_data = self.rate_limits[api_name]
            
            # Clean old requests (1 minute window)
            window_start = current_time - timedelta(minutes=1)
            rate_data["requests"] = [
                req_time for req_time in rate_data["requests"]
                if req_time > window_start
            ]
            
            # Check if under limit
            if len(rate_data["requests"]) >= rate_limit:
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Error checking rate limit for {api_name}: {e}")
            return True  # Allow request on error
    
    async def _update_rate_limit(self, api_name: str):
        """Update rate limit tracking"""
        try:
            current_time = datetime.utcnow()
            
            if api_name in self.rate_limits:
                self.rate_limits[api_name]["requests"].append(current_time)
                
        except Exception as e:
            logging.error(f"Error updating rate limit for {api_name}: {e}")
    
    async def _validate_response_security(self, response: aiohttp.ClientResponse, api_name: str) -> bool:
        """Validate response for security issues"""
        try:
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'application/json' not in content_type and 'text/' not in content_type:
                logging.warning(f"Unexpected content type from {api_name}: {content_type}")
            
            # Check for security headers
            security_headers = [
                'strict-transport-security',
                'x-content-type-options',
                'x-frame-options'
            ]
            
            missing_headers = []
            for header in security_headers:
                if header not in response.headers:
                    missing_headers.append(header)
            
            if missing_headers:
                logging.info(f"Missing security headers from {api_name}: {missing_headers}")
            
            # Check response size (prevent DoS)
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB limit
                logging.warning(f"Large response from {api_name}: {content_length} bytes")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Error validating response security: {e}")
            return True  # Allow response on validation error
    
    def _update_connection_stats(self, api_name: str, success: bool):
        """Update connection statistics"""
        try:
            if api_name not in self.connection_stats:
                self.connection_stats[api_name] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "last_success": None,
                    "last_failure": None,
                    "consecutive_failures": 0
                }
            
            stats = self.connection_stats[api_name]
            stats["total_requests"] += 1
            
            if success:
                stats["successful_requests"] += 1
                stats["last_success"] = datetime.utcnow().isoformat()
                stats["consecutive_failures"] = 0
            else:
                stats["failed_requests"] += 1
                stats["last_failure"] = datetime.utcnow().isoformat()
                stats["consecutive_failures"] += 1
                
                # Track persistent failures
                if stats["consecutive_failures"] >= 5:
                    self._log_security_event("persistent_failures", api_name, 
                                           f"{stats['consecutive_failures']} consecutive failures")
                
        except Exception as e:
            logging.error(f"Error updating connection stats: {e}")
    
    def _log_security_event(self, event_type: str, api_name: str, details: str):
        """Log security events for monitoring"""
        try:
            event = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_type,
                "api_name": api_name,
                "details": details
            }
            
            self.security_events.append(event)
            
            # Keep only recent events (last 1000)
            if len(self.security_events) > 1000:
                self.security_events = self.security_events[-1000:]
            
            # Log critical events
            if event_type in ["ssl_error", "auth_failure", "security_violation"]:
                logging.warning(f"Security event: {event_type} for {api_name} - {details}")
            
            self.security_stats["security_violations"] += 1
            
        except Exception as e:
            logging.error(f"Error logging security event: {e}")
    
    async def validate_api_connections(self) -> Dict[str, Any]:
        """Validate all configured API connections"""
        validation_report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_apis": len(self.api_configs),
            "successful_connections": 0,
            "failed_connections": 0,
            "api_status": {},
            "security_issues": []
        }
        
        for api_name, config in self.api_configs.items():
            try:
                # Test basic connectivity
                test_endpoint = "health" if "health" in config.get("test_endpoints", []) else ""
                
                success, response, error = await self.make_secure_request(
                    api_name, test_endpoint, method="GET"
                )
                
                if success:
                    validation_report["successful_connections"] += 1
                    validation_report["api_status"][api_name] = {
                        "status": "connected",
                        "response_time": "< 30s",
                        "ssl_valid": True
                    }
                else:
                    validation_report["failed_connections"] += 1
                    validation_report["api_status"][api_name] = {
                        "status": "failed",
                        "error": error,
                        "ssl_valid": False
                    }
                    
                    validation_report["security_issues"].append({
                        "api": api_name,
                        "issue": f"Connection failed: {error}"
                    })
                
                # Validate credentials if required
                if config.get("requires_auth", False):
                    auth_type = config.get("auth_type", "api_key")
                    credential = self.credential_manager.get_credential(api_name, auth_type)
                    
                    if not credential:
                        validation_report["security_issues"].append({
                            "api": api_name,
                            "issue": f"Missing {auth_type} credential"
                        })
                        validation_report["api_status"][api_name]["auth_status"] = "missing_credentials"
                    else:
                        validation_report["api_status"][api_name]["auth_status"] = "credentials_available"
                
            except Exception as e:
                validation_report["failed_connections"] += 1
                validation_report["api_status"][api_name] = {
                    "status": "error",
                    "error": str(e)
                }
                
                validation_report["security_issues"].append({
                    "api": api_name,
                    "issue": f"Validation error: {str(e)}"
                })
        
        return validation_report
    
    async def rotate_api_credentials(self, api_name: str, new_credential: str) -> bool:
        """Rotate API credentials for a service"""
        try:
            config = self.api_configs.get(api_name)
            if not config:
                logging.error(f"Unknown API: {api_name}")
                return False
            
            if not config.get("requires_auth", False):
                logging.error(f"API {api_name} does not require authentication")
                return False
            
            auth_type = config.get("auth_type", "api_key")
            
            # Store new credential
            success = self.credential_manager.rotate_credential(api_name, auth_type, new_credential)
            
            if success:
                # Test new credential
                test_success, _, error = await self.make_secure_request(
                    api_name, "test", method="GET"
                )
                
                if test_success:
                    self._log_security_event("credential_rotation", api_name, "Successful rotation")
                    logging.info(f"Successfully rotated credentials for {api_name}")
                    return True
                else:
                    logging.error(f"New credential test failed for {api_name}: {error}")
                    return False
            else:
                logging.error(f"Failed to store new credential for {api_name}")
                return False
                
        except Exception as e:
            logging.error(f"Error rotating credentials for {api_name}: {e}")
            return False
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Get comprehensive security statistics"""
        return {
            "security_stats": self.security_stats.copy(),
            "connection_stats": self.connection_stats.copy(),
            "recent_security_events": self.security_events[-10:],  # Last 10 events
            "rate_limit_status": {
                api_name: {
                    "current_requests": len(data["requests"]),
                    "limit": self.api_configs[api_name].get("rate_limit", 60)
                }
                for api_name, data in self.rate_limits.items()
            },
            "api_configurations": {
                api_name: {
                    "requires_auth": config.get("requires_auth", False),
                    "ssl_verify": config.get("ssl_verify", True),
                    "rate_limit": config.get("rate_limit", 60)
                }
                for api_name, config in self.api_configs.items()
            }
        }
    
    def add_api_configuration(
        self,
        api_name: str,
        base_url: str,
        requires_auth: bool = False,
        auth_type: str = "api_key",
        rate_limit: int = 60,
        allowed_methods: List[str] = None
    ) -> bool:
        """Add new API configuration"""
        try:
            if allowed_methods is None:
                allowed_methods = ["GET"]
            
            # Validate base URL
            if not self._validate_url_security(base_url):
                logging.error(f"Base URL failed security validation: {base_url}")
                return False
            
            self.api_configs[api_name] = {
                "base_url": base_url,
                "requires_auth": requires_auth,
                "auth_type": auth_type,
                "rate_limit": rate_limit,
                "ssl_verify": True,
                "allowed_methods": allowed_methods,
                "security_headers": {
                    "User-Agent": "Aviation-Discord-Bot/1.0",
                    "Accept": "application/json"
                }
            }
            
            logging.info(f"Added API configuration for {api_name}")
            return True
            
        except Exception as e:
            logging.error(f"Error adding API configuration for {api_name}: {e}")
            return False
    
    def remove_api_configuration(self, api_name: str) -> bool:
        """Remove API configuration"""
        try:
            if api_name in self.api_configs:
                del self.api_configs[api_name]
                
                # Clean up related data
                if api_name in self.connection_stats:
                    del self.connection_stats[api_name]
                if api_name in self.rate_limits:
                    del self.rate_limits[api_name]
                
                logging.info(f"Removed API configuration for {api_name}")
                return True
            else:
                logging.warning(f"API configuration not found: {api_name}")
                return False
                
        except Exception as e:
            logging.error(f"Error removing API configuration for {api_name}: {e}")
            return False