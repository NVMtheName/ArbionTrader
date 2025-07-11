#!/usr/bin/env python3
"""
Test DNS propagation status for arbion.ai
"""
import requests
import socket
from urllib.parse import urlparse

def test_dns_status():
    print("=== DNS Status Test ===")
    
    # Test DNS resolution
    try:
        ip = socket.gethostbyname('arbion.ai')
        print(f"arbion.ai resolves to: {ip}")
        
        if ip == '3.33.241.96':
            print("✓ DNS A record is correct")
        else:
            print(f"✗ DNS A record is incorrect. Expected: 3.33.241.96, Got: {ip}")
    except Exception as e:
        print(f"✗ DNS resolution failed: {e}")
    
    # Test WWW subdomain
    try:
        www_ip = socket.gethostbyname('www.arbion.ai')
        print(f"www.arbion.ai resolves to: {www_ip}")
    except Exception as e:
        print(f"✗ WWW DNS resolution failed: {e}")
    
    # Test HTTP connectivity
    domains = ['https://arbion.ai', 'https://www.arbion.ai']
    
    for domain in domains:
        try:
            response = requests.get(domain, timeout=10, verify=False)
            print(f"✓ {domain} - HTTP {response.status_code}")
            
            # Check if it's the correct Heroku app
            if 'Arbion' in response.text or 'Trading Platform' in response.text:
                print(f"  ✓ Correct application content detected")
            else:
                print(f"  ✗ Incorrect application content")
                
        except Exception as e:
            print(f"✗ {domain} - Connection failed: {e}")

if __name__ == "__main__":
    test_dns_status()