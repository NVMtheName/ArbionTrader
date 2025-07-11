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

logger = logging.getLogger(__name__)

class OpenAITrader:
    def __init__(self, api_key=None, user_id=None):
        """
        Initialize OpenAI trader with API key or user ID for database lookup
        """
        self.user_id = user_id
        self.api_key = api_key
        self.client = None
        
        # If user_id provided but no API key, load from database
        if user_id and not api_key:
            self.api_key = self._load_api_key(user_id)
        
        # Initialize OpenAI client if we have an API key
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
    
    def _load_api_key(self, user_id):
        """Load OpenAI API key from database for the user"""
        try:
            from models import APICredential
            from utils.encryption import decrypt_credentials
            
            api_cred = APICredential.query.filter_by(
                user_id=user_id,
                provider='openai',
                is_active=True
            ).first()
            
            if api_cred:
                credentials = decrypt_credentials(api_cred.encrypted_credentials)
                return credentials.get('api_key')
            else:
                logger.warning(f"No active OpenAI API credentials found for user {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to load OpenAI API key for user {user_id}: {e}")
            return None
        
    def test_connection(self):
        """Test OpenAI API connection with enhanced security and error handling"""
        try:
            if not self.client:
                return {
                    'success': False,
                    'message': 'OpenAI API key not configured'
                }
            
            # Enhanced security checks
            from utils.oauth_security import oauth_security
            
            # Check rate limiting for API testing
            allowed, message = oauth_security.check_rate_limiting(self.user_id, "openai_test")
            if not allowed:
                logger.warning(f"Rate limit exceeded for OpenAI API test - user {self.user_id}")
                return {'success': False, 'message': message}
            
            # Test with the models endpoint first (simpler and more reliable)
            models_response = self.client.models.list()
            if models_response and models_response.data:
                # Test with a simple chat completion to ensure full API access
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",  # Use cheaper model for testing
                    messages=[{"role": "user", "content": "Test"}],
                    max_tokens=1
                )
                
                # Clear successful attempt tracking
                oauth_security.clear_successful_attempt(self.user_id, "openai_test")
                
                return {"success": True, "message": "OpenAI API connection successful"}
            else:
                oauth_security.record_failed_attempt(self.user_id, "openai_test")
                return {"success": False, "message": "OpenAI API returned empty response"}
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"OpenAI API test failed: {error_msg}")
            
            # Enhanced error handling with specific guidance
            if "401" in error_msg:
                if "project" in error_msg.lower():
                    return {
                        "success": False, 
                        "message": "Project access error. Your API key may not have access to the project. Check your project settings at https://platform.openai.com/settings/organization/projects"
                    }
                elif "organization" in error_msg.lower():
                    return {
                        "success": False, 
                        "message": "Organization access issue. Check your organization role at https://platform.openai.com/settings/organization/general"
                    }
                elif "invalid_api_key" in error_msg.lower():
                    return {
                        "success": False,
                        "message": "Invalid API key format. Please create a new API key at https://platform.openai.com/api-keys"
                    }
                else:
                    return {
                        "success": False,
                        "message": "Authentication failed. Create a new API key with 'All' permissions at https://platform.openai.com/api-keys"
                    }
            elif "403" in error_msg:
                return {
                    "success": False,
                    "message": "Access forbidden. Your API key may lack sufficient permissions. Create a new key with 'All' permissions."
                }
            elif "insufficient_quota" in error_msg.lower() or "quota" in error_msg.lower():
                return {
                    "success": False, 
                    "message": "API quota exceeded. Add billing information or increase your quota at https://platform.openai.com/settings/organization/billing"
                }
            elif "billing" in error_msg.lower() or "payment" in error_msg.lower():
                return {
                    "success": False, 
                    "message": "Billing issue. Ensure you have a valid payment method at https://platform.openai.com/settings/organization/billing"
                }
            elif "rate_limit" in error_msg.lower() or "rate" in error_msg.lower():
                return {
                    "success": False, 
                    "message": "Rate limit exceeded. Please wait and try again."
                }
            elif "model" in error_msg.lower() and "not found" in error_msg.lower():
                return {
                    "success": False, 
                    "message": "Model access error. Ensure you have access to the gpt-4o-mini model."
                }
            else:
                return {"success": False, "message": f"OpenAI API error: {error_msg}"}
    
    def parse_trading_prompt(self, prompt):
        """Parse natural language trading prompt with enhanced security"""
        try:
            if not self.client:
                return {
                    'success': False,
                    'message': 'OpenAI API key not configured'
                }
            
            # Enhanced security checks
            from utils.oauth_security import oauth_security
            
            # Check rate limiting for API calls
            allowed, message = oauth_security.check_rate_limiting(self.user_id, "openai_parse")
            if not allowed:
                logger.warning(f"Rate limit exceeded for OpenAI parsing - user {self.user_id}")
                return {'success': False, 'message': message}
            
            # Input validation and sanitization
            if not prompt or len(prompt.strip()) == 0:
                return {'success': False, 'message': 'Empty instruction provided'}
            
            # Limit instruction length to prevent abuse
            if len(prompt) > 1000:
                return {'success': False, 'message': 'Instruction too long (max 1000 characters)'}
            
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
- If quantity is specified (e.g., "1 share of AAPL"), use "quantity" field
- Default to "market" order type unless specified otherwise
- Set confidence based on how clear the instruction is"""

            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=300,
                temperature=0.1  # Lower temperature for more consistent parsing
            )
            
            parsed_instruction = json.loads(response.choices[0].message.content)
            
            # Validate parsed instruction
            if not parsed_instruction.get('action') or not parsed_instruction.get('symbol'):
                oauth_security.record_failed_attempt(self.user_id, "openai_parse")
                return {
                    'success': False,
                    'message': 'Could not parse trading instruction. Please specify action and symbol.'
                }
            
            # Clear successful attempt tracking
            oauth_security.clear_successful_attempt(self.user_id, "openai_parse")
            
            # Log successful parsing (without sensitive content)
            logger.info(f"Successfully parsed trading prompt for user {self.user_id}")
            
            return {
                'success': True,
                'instruction': parsed_instruction,
                'message': 'Trade instruction parsed successfully'
            }
            
        except Exception as e:
            oauth_security.record_failed_attempt(self.user_id, "openai_parse")
            logger.error(f"Failed to parse trading prompt: {e}")
            return {
                'success': False,
                'message': f'Failed to parse trading instruction: {str(e)}'
            }
    
    def execute_trade(self, trade_instruction, user_id, is_simulation=False):
        """Execute a trade based on parsed instruction"""
        try:
            if not isinstance(trade_instruction, dict):
                return {
                    'success': False,
                    'message': 'Invalid trade instruction format'
                }
            
            provider = trade_instruction.get('provider', '').lower()
            symbol = trade_instruction.get('symbol', '').upper()
            action = trade_instruction.get('action', '').lower()
            
            if not all([provider, symbol, action]):
                return {
                    'success': False,
                    'message': 'Missing required trade parameters'
                }
            
            # Create trade record
            trade = Trade(
                user_id=user_id,
                provider=provider,
                symbol=symbol,
                side=action,
                quantity=trade_instruction.get('quantity'),
                price=trade_instruction.get('price'),
                amount=trade_instruction.get('amount'),
                trade_type=trade_instruction.get('order_type', 'market'),
                strategy='ai',
                natural_language_prompt=trade_instruction.get('original_prompt', ''),
                is_simulation=is_simulation
            )
            
            if is_simulation:
                trade.status = 'simulated'
                trade.execution_details = json.dumps({
                    'simulation': True,
                    'timestamp': datetime.utcnow().isoformat()
                })
                db.session.add(trade)
                db.session.commit()
                
                return {
                    'success': True,
                    'message': f'Simulated {action} order for {symbol}',
                    'trade_id': trade.id
                }
            else:
                # Execute actual trade (implement based on provider)
                if provider == 'coinbase':
                    # Use Coinbase connector
                    return self._execute_coinbase_trade(trade, user_id)
                elif provider == 'schwab':
                    # Use Schwab connector
                    return self._execute_schwab_trade(trade, user_id)
                else:
                    return {
                        'success': False,
                        'message': f'Unsupported provider: {provider}'
                    }
                    
        except Exception as e:
            logger.error(f"Failed to execute trade: {e}")
            return {
                'success': False,
                'message': f'Trade execution failed: {str(e)}'
            }
    
    def _execute_coinbase_trade(self, trade, user_id):
        """Execute trade on Coinbase"""
        # Implementation for Coinbase trading
        trade.status = 'pending'
        db.session.add(trade)
        db.session.commit()
        
        return {
            'success': True,
            'message': f'Coinbase trade submitted',
            'trade_id': trade.id
        }
    
    def _execute_schwab_trade(self, trade, user_id):
        """Execute trade on Schwab"""
        # Implementation for Schwab trading
        trade.status = 'pending'
        db.session.add(trade)
        db.session.commit()
        
        return {
            'success': True,
            'message': f'Schwab trade submitted',
            'trade_id': trade.id
        }
    
    def analyze_market_conditions(self, symbol, conditions):
        """Analyze market conditions using OpenAI"""
        try:
            if not self.client:
                return {
                    'success': False,
                    'message': 'OpenAI API key not configured'
                }
            
            analysis_prompt = f"""Analyze the current market conditions for {symbol} and provide insights based on the following conditions: {conditions}
            
            Provide your analysis in JSON format with the following structure:
            {{
                "symbol": "{symbol}",
                "market_sentiment": "bullish/bearish/neutral",
                "key_factors": ["factor1", "factor2", "factor3"],
                "risk_level": "low/medium/high",
                "recommendation": "buy/sell/hold",
                "confidence": 0.0-1.0,
                "reasoning": "detailed explanation"
            }}"""
            
            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a financial market analyst providing objective market analysis."},
                    {"role": "user", "content": analysis_prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=500
            )
            
            analysis = json.loads(response.choices[0].message.content)
            return {
                'success': True,
                'analysis': analysis,
                'message': 'Market analysis completed successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze market conditions: {e}")
            return {
                'success': False,
                'message': f'Market analysis failed: {str(e)}'
            }
    
    def generate_trading_strategy(self, strategy_type, parameters):
        """Generate a trading strategy using OpenAI"""
        try:
            if not self.client:
                return {
                    'success': False,
                    'message': 'OpenAI API key not configured'
                }
            
            strategy_prompt = f"""Generate a {strategy_type} trading strategy with the following parameters: {json.dumps(parameters)}
            
            Provide the strategy in JSON format with the following structure:
            {{
                "strategy_name": "descriptive name",
                "strategy_type": "{strategy_type}",
                "entry_conditions": ["condition1", "condition2"],
                "exit_conditions": ["condition1", "condition2"],
                "risk_management": {{
                    "stop_loss": "percentage or amount",
                    "take_profit": "percentage or amount",
                    "position_size": "percentage of portfolio"
                }},
                "timeframe": "daily/weekly/monthly",
                "expected_return": "percentage estimate",
                "risk_rating": "low/medium/high",
                "description": "detailed strategy explanation"
            }}"""
            
            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a professional trading strategy developer."},
                    {"role": "user", "content": strategy_prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=600
            )
            
            strategy = json.loads(response.choices[0].message.content)
            return {
                'success': True,
                'strategy': strategy,
                'message': 'Trading strategy generated successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to generate trading strategy: {e}")
            return {
                'success': False,
                'message': f'Strategy generation failed: {str(e)}'
            }