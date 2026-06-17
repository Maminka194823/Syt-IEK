#!/usr/bin/env python3
"""
Token Test - Test if the Discord token is valid
"""

import os
import requests

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def test_discord_token():
    """Test if Discord token is valid"""
    token = os.getenv('DISCORD_TOKEN') or os.getenv('DISCORD_BOT_TOKEN') or os.getenv('AVIATION_BOT_DISCORD_TOKEN')
    
    if not token:
        print("  No token found")
        return False
    
    print(f"🔑 Testing token: {token[:20]}...")
    
    # Test token with Discord API
    headers = {
        'Authorization': f'Bot {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get('https://discord.com/api/v10/users/@me', headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Token is valid!")
            print(f"   Bot name: {data.get('username')}")
            print(f"   Bot ID: {data.get('id')}")
            return True
        elif response.status_code == 401:
            print("  Token is invalid or expired")
            return False
        else:
            print(f"  API error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"  Error testing token: {e}")
        return False

if __name__ == "__main__":
    test_discord_token()