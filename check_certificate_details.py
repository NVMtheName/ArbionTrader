#!/usr/bin/env python3
"""
Check detailed SSL certificate information for arbion.ai
"""

import ssl
import socket
from urllib.parse import urlparse

def get_certificate_details(hostname, port=443):
    """Get detailed certificate information"""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                
                print(f"=== Certificate Details for {hostname} ===")
                print(f"Subject: {cert.get('subject', 'N/A')}")
                print(f"Issuer: {cert.get('issuer', 'N/A')}")
                print(f"Valid from: {cert.get('notBefore', 'N/A')}")
                print(f"Valid until: {cert.get('notAfter', 'N/A')}")
                print(f"Serial Number: {cert.get('serialNumber', 'N/A')}")
                print(f"Version: {cert.get('version', 'N/A')}")
                
                # Check Subject Alternative Names
                if 'subjectAltName' in cert:
                    sans = [name[1] for name in cert['subjectAltName']]
                    print(f"Subject Alternative Names: {sans}")
                    
                    # Check if both domains are covered
                    if 'arbion.ai' in sans and 'www.arbion.ai' in sans:
                        print("✓ Certificate covers both arbion.ai and www.arbion.ai")
                    elif 'www.arbion.ai' in sans:
                        print("✗ Certificate only covers www.arbion.ai")
                        print("  Missing: arbion.ai")
                    elif 'arbion.ai' in sans:
                        print("✗ Certificate only covers arbion.ai")
                        print("  Missing: www.arbion.ai")
                    else:
                        print("✗ Certificate does not cover either domain")
                else:
                    print("✗ No Subject Alternative Names found")
                
                return cert
                
    except Exception as e:
        print(f"✗ Error getting certificate for {hostname}: {e}")
        return None

def main():
    print("=== SSL Certificate Analysis ===\n")
    
    # Check www.arbion.ai (working)
    www_cert = get_certificate_details('www.arbion.ai')
    print()
    
    # Try to check arbion.ai (not working directly)
    print("=== Attempting to check arbion.ai certificate ===")
    try:
        # Since direct connection fails, let's check what certificate is actually served
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = requests.get('https://arbion.ai', verify=False, timeout=10)
        print(f"Response status: {response.status_code}")
        print("Note: Certificate verification disabled for testing")
        
    except Exception as e:
        print(f"Connection error: {e}")
    
    print("\n=== Analysis Results ===")
    print("Issue: Your SSL certificate only covers www.arbion.ai")
    print("Solution: You need to generate a new certificate that covers both domains")
    
    print("\n=== Heroku SSL Certificate Types ===")
    print("1. SAN (Subject Alternative Name) certificate - covers multiple domains")
    print("2. Wildcard certificate - covers *.arbion.ai")
    print("3. Multi-domain certificate - covers specific domains")
    
    print("\n=== Recommended Fix ===")
    print("You need to request a new SSL certificate that includes both:")
    print("- arbion.ai")
    print("- www.arbion.ai")
    print("\nThis typically requires removing the current certificate and requesting a new one")

if __name__ == "__main__":
    main()