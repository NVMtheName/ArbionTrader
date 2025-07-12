#!/usr/bin/env python3
"""
Check SSL certificate status for arbion.ai domain
"""

import socket
import ssl
import requests
import subprocess
import sys
from urllib.parse import urlparse

def check_dns_resolution(domain):
    """Check if domain resolves to correct IP"""
    try:
        ip = socket.gethostbyname(domain)
        print(f"✓ {domain} resolves to: {ip}")
        return ip
    except socket.gaierror as e:
        print(f"✗ DNS resolution failed for {domain}: {e}")
        return None

def check_ssl_certificate(domain, port=443):
    """Check SSL certificate for domain"""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                print(f"✓ SSL certificate found for {domain}")
                print(f"  Subject: {cert.get('subject', 'N/A')}")
                print(f"  Issuer: {cert.get('issuer', 'N/A')}")
                print(f"  Valid from: {cert.get('notBefore', 'N/A')}")
                print(f"  Valid until: {cert.get('notAfter', 'N/A')}")
                
                # Check if certificate matches domain
                san_list = []
                if 'subjectAltName' in cert:
                    san_list = [name[1] for name in cert['subjectAltName']]
                
                if domain in san_list or any(domain in str(subject) for subject in cert.get('subject', [])):
                    print(f"  ✓ Certificate matches domain {domain}")
                else:
                    print(f"  ✗ Certificate does not match domain {domain}")
                    print(f"  Certificate SAN: {san_list}")
                
                return True
    except ssl.SSLError as e:
        print(f"✗ SSL error for {domain}: {e}")
        return False
    except Exception as e:
        print(f"✗ Connection error for {domain}: {e}")
        return False

def check_http_redirect(domain):
    """Check if HTTP redirects to HTTPS"""
    try:
        response = requests.get(f"http://{domain}", timeout=10, allow_redirects=False)
        if response.status_code in [301, 302, 307, 308]:
            location = response.headers.get('location', '')
            if location.startswith('https://'):
                print(f"✓ HTTP redirects to HTTPS: {location}")
                return True
            else:
                print(f"✗ HTTP redirects to: {location} (not HTTPS)")
                return False
        else:
            print(f"✗ HTTP does not redirect (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"✗ HTTP redirect check failed: {e}")
        return False

def check_https_accessibility(domain):
    """Check if HTTPS site is accessible"""
    try:
        response = requests.get(f"https://{domain}", timeout=10, verify=True)
        print(f"✓ HTTPS site accessible (status: {response.status_code})")
        return True
    except requests.exceptions.SSLError as e:
        print(f"✗ HTTPS SSL error: {e}")
        return False
    except Exception as e:
        print(f"✗ HTTPS accessibility error: {e}")
        return False

def main():
    domain = "arbion.ai"
    www_domain = f"www.{domain}"
    
    print(f"=== SSL Certificate Status Check for {domain} ===\n")
    
    # Check DNS resolution
    print("1. DNS Resolution:")
    root_ip = check_dns_resolution(domain)
    www_ip = check_dns_resolution(www_domain)
    print()
    
    # Check SSL certificates
    print("2. SSL Certificate Check:")
    root_ssl = check_ssl_certificate(domain)
    www_ssl = check_ssl_certificate(www_domain)
    print()
    
    # Check HTTP to HTTPS redirect
    print("3. HTTP to HTTPS Redirect:")
    root_redirect = check_http_redirect(domain)
    www_redirect = check_http_redirect(www_domain)
    print()
    
    # Check HTTPS accessibility
    print("4. HTTPS Accessibility:")
    root_https = check_https_accessibility(domain)
    www_https = check_https_accessibility(www_domain)
    print()
    
    # Summary
    print("=== Summary ===")
    if root_ssl and root_https:
        print(f"✓ {domain} SSL is working correctly")
    else:
        print(f"✗ {domain} SSL has issues")
        
    if www_ssl and www_https:
        print(f"✓ {www_domain} SSL is working correctly")
    else:
        print(f"✗ {www_domain} SSL has issues")
    
    # Recommendations
    print("\n=== Recommendations ===")
    if not root_ssl or not root_https:
        print("- Check DNS CNAME records point to Heroku")
        print("- Verify SSL certificate is properly configured in Heroku")
        print("- Ensure domain is added to Heroku app")
    
    if not root_redirect:
        print("- Configure HTTP to HTTPS redirect in Heroku")

if __name__ == "__main__":
    main()