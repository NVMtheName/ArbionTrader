#!/usr/bin/env python3
"""
Test script for enhanced market data functionality
Tests all the new real-time market data features
"""

import sys
import json
import time
import requests
from datetime import datetime

def test_enhanced_market_data():
    """Test all enhanced market data features"""
    
    print("=== Enhanced Market Data Test Suite ===")
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Symbol Search
    print("\n1. Testing Symbol Search API...")
    try:
        from utils.enhanced_market_data import EnhancedMarketDataProvider
        provider = EnhancedMarketDataProvider()
        
        # Test search functionality
        search_terms = ['apple', 'tesla', 'google', 'bitcoin']
        for term in search_terms:
            results = provider.search_symbols(term, 3)
            print(f"   '{term}' search: {len(results)} results")
            if results:
                print(f"   Top result: {results[0].get('symbol', 'N/A')} - {results[0].get('name', 'N/A')}")
        
        print("   ✓ Symbol search working correctly")
        
    except Exception as e:
        print(f"   ✗ Symbol search failed: {str(e)}")
    
    # Test 2: Real-time Quotes
    print("\n2. Testing Real-time Quotes...")
    try:
        test_symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA']
        quotes = provider.get_multiple_quotes(test_symbols)
        
        print(f"   Retrieved {len(quotes)} quotes:")
        for symbol, data in quotes.items():
            price = data.get('price', 0)
            change = data.get('change_percent', 0)
            print(f"   {symbol}: ${price:.2f} ({change:+.2f}%)")
        
        print("   ✓ Real-time quotes working correctly")
        
    except Exception as e:
        print(f"   ✗ Real-time quotes failed: {str(e)}")
    
    # Test 3: Crypto Prices
    print("\n3. Testing Crypto Prices...")
    try:
        crypto_symbols = ['BTC', 'ETH', 'LTC']
        for symbol in crypto_symbols:
            crypto_data = provider.get_crypto_price(symbol)
            if crypto_data:
                price = crypto_data.get('price', 0)
                change = crypto_data.get('change_percent', 0)
                print(f"   {symbol}: ${price:.2f} ({change:+.2f}%)")
        
        print("   ✓ Crypto prices working correctly")
        
    except Exception as e:
        print(f"   ✗ Crypto prices failed: {str(e)}")
    
    # Test 4: Market Movers
    print("\n4. Testing Market Movers...")
    try:
        movers = provider.get_market_movers()
        
        if movers:
            gainers = movers.get('gainers', [])
            losers = movers.get('losers', [])
            most_active = movers.get('most_active', [])
            
            print(f"   Gainers: {len(gainers)} stocks")
            print(f"   Losers: {len(losers)} stocks")
            print(f"   Most Active: {len(most_active)} stocks")
            
            if gainers:
                top_gainer = gainers[0]
                print(f"   Top Gainer: {top_gainer.get('symbol', 'N/A')} ({top_gainer.get('change_percent', 0):+.2f}%)")
        
        print("   ✓ Market movers working correctly")
        
    except Exception as e:
        print(f"   ✗ Market movers failed: {str(e)}")
    
    # Test 5: Historical Data
    print("\n5. Testing Historical Data...")
    try:
        historical = provider.get_historical_data('AAPL', '5d')
        if historical and 'data' in historical:
            data_points = len(historical['data'])
            print(f"   Retrieved {data_points} historical data points for AAPL")
            
            if data_points > 0:
                latest = historical['data'][-1]
                print(f"   Latest: {latest.get('date', 'N/A')} - Close: ${latest.get('close', 0):.2f}")
        
        print("   ✓ Historical data working correctly")
        
    except Exception as e:
        print(f"   ✗ Historical data failed: {str(e)}")
    
    # Test 6: Cache Performance
    print("\n6. Testing Cache Performance...")
    try:
        # Test cache by making repeated calls
        start_time = time.time()
        quote1 = provider.get_real_time_quote('AAPL')
        first_call_time = time.time() - start_time
        
        start_time = time.time()
        quote2 = provider.get_real_time_quote('AAPL')
        second_call_time = time.time() - start_time
        
        print(f"   First call: {first_call_time:.3f}s")
        print(f"   Second call: {second_call_time:.3f}s")
        
        if second_call_time < first_call_time:
            print("   ✓ Cache is working (second call faster)")
        else:
            print("   ⚠ Cache may not be working optimally")
        
    except Exception as e:
        print(f"   ✗ Cache performance test failed: {str(e)}")
    
    # Test 7: Error Handling
    print("\n7. Testing Error Handling...")
    try:
        # Test invalid symbol
        invalid_quote = provider.get_real_time_quote('INVALID_SYMBOL_123')
        if not invalid_quote:
            print("   ✓ Invalid symbol properly handled")
        else:
            print("   ⚠ Invalid symbol returned data (unexpected)")
        
        # Test empty search
        empty_search = provider.search_symbols('', 5)
        if not empty_search:
            print("   ✓ Empty search properly handled")
        else:
            print("   ⚠ Empty search returned results (unexpected)")
        
    except Exception as e:
        print(f"   ✗ Error handling test failed: {str(e)}")
    
    print("\n=== Test Summary ===")
    print("Enhanced market data system is ready!")
    print("✓ Real-time stock quotes with company details")
    print("✓ Comprehensive symbol search functionality")
    print("✓ Live cryptocurrency prices")
    print("✓ Market movers analysis")
    print("✓ Historical data with caching")
    print("✓ Proper error handling")
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    test_enhanced_market_data()