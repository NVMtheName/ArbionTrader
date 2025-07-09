import os
import json
import logging
from datetime import datetime
from openai import OpenAI
from models import Trade
from app import db
from utils.coinbase_connector import CoinbaseConnector
from utils.schwab_connector import SchwabConnector
from utils.encryption import decrypt_credentials
from models import APICredential

class OpenAITrader:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key)
        
    def test_connection(self):
        """Test OpenAI API connection"""
        try:
            # Simple test with minimal token usage
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Use cheaper model for testing
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1
            )
            return {"success": True, "message": "OpenAI API connection successful"}
        except Exception as e:
            error_msg = str(e)
            
            # Provide specific guidance for common errors
            if "401" in error_msg and "missing_scope" in error_msg:
                return {
                    "success": False, 
                    "message": "API key lacks required permissions. Create a new API key with 'All' permissions at https://platform.openai.com/api-keys. Ensure you have Writer/Owner role in your organization."
                }
            elif "401" in error_msg and "organization" in error_msg.lower():
                return {
                    "success": False, 
                    "message": "Organization access issue. Check your organization role at https://platform.openai.com/settings/organization/general"
                }
            elif "401" in error_msg:
                return {
                    "success": False, 
                    "message": "Invalid API key. Create a new API key at https://platform.openai.com/api-keys"
                }
            elif "quota" in error_msg.lower() or "billing" in error_msg.lower():
                return {
                    "success": False, 
                    "message": "API quota exceeded or billing issue. Check your usage at https://platform.openai.com/usage"
                }
            elif "rate" in error_msg.lower():
                return {
                    "success": False, 
                    "message": "Rate limit exceeded. Please wait and try again."
                }
            else:
                return {"success": False, "message": f"OpenAI API connection failed: {error_msg}"}
    
    def parse_trading_prompt(self, prompt):
        """Parse natural language trading prompt into structured instructions"""
        try:
            system_prompt = """You are an AI trading assistant that converts natural language trading instructions into structured JSON format.

Parse the user's trading request and return a JSON object with the following structure:
{
    "action": "buy" or "sell",
    "symbol": "stock/crypto symbol",
    "quantity": number or null,
    "amount": dollar amount or null,
    "order_type": "market" or "limit" or "stop",
    "price": limit price or null,
    "provider": "coinbase" or "schwab" (determine based on symbol),
    "conditions": "any conditional logic described",
    "confidence": number between 0 and 1
}

Rules:
- For crypto symbols (BTC, ETH, etc.), use "coinbase" provider
- For stocks (AAPL, MSFT, etc.), use "schwab" provider
- If amount is specified (e.g., "$200 of ETH"), use "amount" field
- If quantity is specified (e.g., "10 shares"), use "quantity" field
- Default to "market" order type unless specific price is mentioned
- Extract any conditional logic (MACD, RSI, etc.) into conditions field
- Set confidence based on how clear and specific the instruction is

Examples:
- "Buy $200 of ETH" -> {"action": "buy", "symbol": "ETH-USD", "amount": 200, "order_type": "market", "provider": "coinbase"}
- "Sell 10 shares of AAPL at $150" -> {"action": "sell", "symbol": "AAPL", "quantity": 10, "price": 150, "order_type": "limit", "provider": "schwab"}
- "Buy BTC if price drops below $40000" -> {"action": "buy", "symbol": "BTC-USD", "order_type": "limit", "price": 40000, "provider": "coinbase", "conditions": "price drops below $40000"}

Return only valid JSON, no other text."""

            response = self.client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=500
            )
            
            result = json.loads(response.choices[0].message.content)
            result['original_prompt'] = prompt
            
            logging.info(f"Parsed trading prompt: {prompt} -> {result}")
            return result
        
        except Exception as e:
            logging.error(f"Error parsing trading prompt: {str(e)}")
            raise Exception(f"Failed to parse trading instruction: {str(e)}")
    
    def execute_trade(self, trade_instruction, user_id, is_simulation=False):
        """Execute a trade based on parsed instruction"""
        try:
            provider = trade_instruction.get('provider')
            symbol = trade_instruction.get('symbol')
            action = trade_instruction.get('action')
            quantity = trade_instruction.get('quantity')
            amount = trade_instruction.get('amount')
            order_type = trade_instruction.get('order_type', 'market')
            price = trade_instruction.get('price')
            
            # Validate required fields
            if not all([provider, symbol, action]):
                raise ValueError("Missing required fields: provider, symbol, or action")
            
            if action not in ['buy', 'sell']:
                raise ValueError("Invalid action, must be 'buy' or 'sell'")
            
            # Get user's API credentials for the provider
            api_cred = APICredential.query.filter_by(
                user_id=user_id,
                provider=provider,
                is_active=True
            ).first()
            
            if not api_cred:
                raise ValueError(f"No {provider} API credentials found for user")
            
            # Decrypt credentials
            credentials = decrypt_credentials(api_cred.encrypted_credentials)
            
            # Execute trade based on provider
            if provider == 'coinbase':
                connector = CoinbaseConnector(
                    credentials['api_key'],
                    credentials['secret'],
                    credentials['passphrase']
                )
                
                if order_type == 'market':
                    result = connector.place_market_order(
                        product_id=symbol,
                        side=action,
                        size=quantity,
                        funds=amount,
                        user_id=user_id,
                        is_simulation=is_simulation
                    )
                elif order_type == 'limit':
                    if not price:
                        raise ValueError("Price is required for limit orders")
                    result = connector.place_limit_order(
                        product_id=symbol,
                        side=action,
                        size=quantity,
                        price=price,
                        user_id=user_id,
                        is_simulation=is_simulation
                    )
                else:
                    raise ValueError("Unsupported order type for Coinbase")
            
            elif provider == 'schwab':
                connector = SchwabConnector(
                    credentials['api_key'],
                    credentials['secret']
                )
                
                # For Schwab, we need to get the first account
                accounts = connector.get_accounts()
                if not accounts:
                    raise ValueError("No Schwab accounts found")
                
                account_id = accounts[0]['accountId']
                
                result = connector.place_equity_order(
                    account_id=account_id,
                    symbol=symbol,
                    quantity=quantity,
                    side=action.upper(),
                    order_type=order_type.upper(),
                    price=price,
                    user_id=user_id,
                    is_simulation=is_simulation
                )
            
            else:
                raise ValueError(f"Unsupported provider: {provider}")
            
            # Update trade record with natural language prompt
            if result.get('trade_id'):
                trade = Trade.query.get(result['trade_id'])
                if trade:
                    trade.natural_language_prompt = trade_instruction.get('original_prompt')
                    trade.strategy = 'ai'
                    db.session.commit()
            
            return result
        
        except Exception as e:
            logging.error(f"Error executing trade: {str(e)}")
            return {
                'success': False,
                'message': f'Trade execution failed: {str(e)}'
            }
    
    def analyze_market_conditions(self, symbol, conditions):
        """Analyze market conditions using OpenAI"""
        try:
            system_prompt = """You are a market analysis expert. Analyze the given market conditions and provide insights.

Return your analysis in JSON format with the following structure:
{
    "analysis": "detailed analysis of the conditions",
    "recommendation": "buy", "sell", or "hold",
    "confidence": number between 0 and 1,
    "reasoning": "explanation of the recommendation"
}

Focus on technical analysis indicators mentioned in the conditions."""

            user_prompt = f"Analyze the market conditions for {symbol}: {conditions}"
            
            response = self.client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=500
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
        
        except Exception as e:
            logging.error(f"Error analyzing market conditions: {str(e)}")
            return {
                'analysis': 'Analysis failed',
                'recommendation': 'hold',
                'confidence': 0.0,
                'reasoning': f'Error: {str(e)}'
            }
    
    def generate_trading_strategy(self, strategy_type, parameters):
        """Generate a trading strategy using OpenAI"""
        try:
            system_prompt = """You are a quantitative trading strategy expert. Generate a detailed trading strategy based on the given type and parameters.

Return your strategy in JSON format with the following structure:
{
    "strategy_name": "descriptive name",
    "description": "detailed description",
    "entry_conditions": "when to enter trades",
    "exit_conditions": "when to exit trades",
    "risk_management": "risk management rules",
    "parameters": {
        "key": "value pairs of strategy parameters"
    },
    "expected_return": "estimated return characteristics",
    "risk_level": "low", "medium", or "high"
}

Focus on creating practical, executable strategies."""

            user_prompt = f"Generate a {strategy_type} trading strategy with these parameters: {json.dumps(parameters)}"
            
            response = self.client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=1000
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
        
        except Exception as e:
            logging.error(f"Error generating trading strategy: {str(e)}")
            return {
                'strategy_name': 'Strategy Generation Failed',
                'description': f'Error: {str(e)}',
                'entry_conditions': 'N/A',
                'exit_conditions': 'N/A',
                'risk_management': 'N/A',
                'parameters': {},
                'expected_return': 'N/A',
                'risk_level': 'high'
            }
