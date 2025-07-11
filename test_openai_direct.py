#!/usr/bin/env python3
"""
Direct test of OpenAI API connection to diagnose authentication issues
"""
import sys
from openai import OpenAI

def test_openai_key(api_key):
    """Test OpenAI API key directly"""
    try:
        client = OpenAI(api_key=api_key)
        
        # First test: List models (minimal permissions required)
        print("Testing models endpoint...")
        models_response = client.models.list()
        print(f"✓ Models endpoint successful: {len(models_response.data)} models available")
        
        # Second test: Simple chat completion
        print("Testing chat completion...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1
        )
        print(f"✓ Chat completion successful: {response.choices[0].message.content}")
        
        return True
        
    except Exception as e:
        print(f"✗ OpenAI API Error: {e}")
        print(f"Error type: {type(e)}")
        
        # Analyze the error
        error_str = str(e)
        if "401" in error_str:
            print("→ This is a 401 Unauthorized error")
            if "project" in error_str.lower():
                print("→ Issue: Project access problem")
                print("→ Solution: Check your project settings")
            elif "organization" in error_str.lower():
                print("→ Issue: Organization access problem")
                print("→ Solution: Check your organization role")
            else:
                print("→ Issue: Invalid API key or insufficient permissions")
                print("→ Solution: Create a new API key with 'All' permissions")
        elif "403" in error_str:
            print("→ This is a 403 Forbidden error")
            print("→ Issue: Insufficient permissions")
        elif "quota" in error_str.lower() or "billing" in error_str.lower():
            print("→ Issue: Quota or billing problem")
            print("→ Solution: Check your billing settings")
        
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_openai_direct.py <api_key>")
        sys.exit(1)
    
    api_key = sys.argv[1]
    success = test_openai_key(api_key)
    
    if success:
        print("\n✅ OpenAI API connection successful!")
    else:
        print("\n❌ OpenAI API connection failed!")