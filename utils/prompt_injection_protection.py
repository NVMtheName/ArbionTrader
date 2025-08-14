"""
OpenAI Prompt Injection Protection
Comprehensive protection against prompt injection attacks for trading instructions
"""

import re
import logging
from typing import Tuple, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class PromptInjectionProtector:
    """Comprehensive prompt injection protection for OpenAI trading instructions"""
    
    def __init__(self):
        # Dangerous patterns that could indicate injection attempts
        self.injection_patterns = [
            # Direct instruction overrides
            r'ignore\s+(previous|all|above|prior)\s+(instructions?|prompts?|commands?)',
            r'forget\s+(everything|all|previous|above)',
            r'disregard\s+(previous|all|above|prior)',
            r'override\s+(previous|all|above|prior)',
            
            # Role manipulation
            r'you\s+are\s+now\s+(?:a|an|the)',
            r'pretend\s+(?:to\s+be|you\s+are)',
            r'act\s+as\s+(?:a|an|the)',
            r'roleplay\s+as',
            r'simulate\s+(?:being|a|an)',
            
            # System prompt manipulation
            r'system\s*[:>]\s*',
            r'<\s*system\s*>',
            r'\[system\]',
            r'assistant\s*[:>]\s*',
            r'<\s*assistant\s*>',
            
            # Code execution attempts
            r'execute\s+(?:code|script|command)',
            r'run\s+(?:code|script|command)',
            r'eval\s*\(',
            r'exec\s*\(',
            r'import\s+os',
            r'import\s+subprocess',
            
            # Data exfiltration attempts
            r'show\s+me\s+(?:the|your|all)',
            r'reveal\s+(?:the|your|all)',
            r'tell\s+me\s+about\s+(?:the|your)',
            r'what\s+(?:is|are)\s+(?:the|your)',
            
            # Financial manipulation attempts
            r'buy\s+everything',
            r'sell\s+everything',
            r'max\s+(?:buy|sell|trade)',
            r'all\s+(?:in|money|funds)',
            r'liquidate\s+(?:all|everything)',
            
            # Suspicious special characters and encodings
            r'\\x[0-9a-fA-F]{2}',  # Hex encoding
            r'\\u[0-9a-fA-F]{4}',  # Unicode encoding
            r'%[0-9a-fA-F]{2}',    # URL encoding
            r'&#\d+;',             # HTML entities
            
            # Template injection
            r'\{\{.*?\}\}',
            r'\{%.*?%\}',
            r'\$\{.*?\}',
            
            # SQL injection patterns (just in case)
            r'union\s+select',
            r'drop\s+table',
            r'delete\s+from',
            r'insert\s+into',
            
            # Command injection
            r';\s*(?:rm|del|format)',
            r'\|\s*(?:curl|wget|nc)',
            r'&&\s*(?:rm|del|format)',
        ]
        
        # Compile patterns for efficiency
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE | re.DOTALL) 
                                for pattern in self.injection_patterns]
        
        # Maximum allowed prompt length
        self.max_prompt_length = 2000
        
        # Whitelist of allowed trading keywords
        self.trading_keywords = {
            'buy', 'sell', 'trade', 'purchase', 'acquire', 'dispose',
            'stock', 'share', 'shares', 'crypto', 'cryptocurrency', 'bitcoin',
            'ethereum', 'portfolio', 'position', 'holdings', 'balance',
            'market', 'price', 'limit', 'stop', 'loss', 'gain', 'profit',
            'analysis', 'analyze', 'research', 'trend', 'technical',
            'fundamental', 'support', 'resistance', 'volume', 'volatility',
            'dividend', 'earnings', 'options', 'call', 'put', 'strike'
        }
    
    def validate_prompt(self, prompt: str, user_id: str = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Comprehensive prompt validation and injection protection
        
        Args:
            prompt: User's trading instruction prompt
            user_id: User identifier for logging
            
        Returns:
            Tuple of (is_safe, sanitized_prompt, analysis_report)
        """
        try:
            analysis_report = {
                'timestamp': datetime.utcnow().isoformat(),
                'original_length': len(prompt),
                'user_id': user_id,
                'detected_issues': [],
                'risk_level': 'low',
                'sanitization_applied': False
            }
            
            # 1. Basic validation
            if not prompt or not prompt.strip():
                return False, "", {**analysis_report, 'detected_issues': ['Empty prompt']}
            
            # 2. Length validation
            if len(prompt) > self.max_prompt_length:
                analysis_report['detected_issues'].append(f'Prompt too long: {len(prompt)} > {self.max_prompt_length}')
                analysis_report['risk_level'] = 'medium'
            
            # 3. Injection pattern detection
            detected_patterns = []
            for i, pattern in enumerate(self.compiled_patterns):
                matches = pattern.findall(prompt)
                if matches:
                    detected_patterns.append({
                        'pattern_index': i,
                        'pattern': self.injection_patterns[i],
                        'matches': matches[:3]  # Limit matches for logging
                    })
            
            if detected_patterns:
                analysis_report['detected_issues'].append('Potential injection patterns detected')
                analysis_report['detected_patterns'] = detected_patterns
                analysis_report['risk_level'] = 'high'
                
                logger.warning(f"Prompt injection attempt detected for user {user_id}: {detected_patterns}")
                return False, "", analysis_report
            
            # 4. Sanitization
            sanitized_prompt = self._sanitize_prompt(prompt)
            if sanitized_prompt != prompt:
                analysis_report['sanitization_applied'] = True
                analysis_report['sanitized_length'] = len(sanitized_prompt)
            
            # 5. Content analysis
            content_analysis = self._analyze_content(sanitized_prompt)
            analysis_report['content_analysis'] = content_analysis
            
            if content_analysis['suspicious_score'] > 0.7:
                analysis_report['risk_level'] = 'high'
                analysis_report['detected_issues'].append('High suspicious content score')
                logger.warning(f"High suspicious content score for user {user_id}: {content_analysis['suspicious_score']}")
                return False, "", analysis_report
            
            return True, sanitized_prompt, analysis_report
            
        except Exception as e:
            logger.error(f"Error validating prompt: {e}")
            return False, "", {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'risk_level': 'high'
            }
    
    def _sanitize_prompt(self, prompt: str) -> str:
        """Sanitize prompt by removing dangerous content"""
        try:
            sanitized = prompt
            
            # Remove potential encoding attempts
            sanitized = re.sub(r'\\x[0-9a-fA-F]{2}', '', sanitized)
            sanitized = re.sub(r'\\u[0-9a-fA-F]{4}', '', sanitized)
            sanitized = re.sub(r'%[0-9a-fA-F]{2}', '', sanitized)
            sanitized = re.sub(r'&#\d+;', '', sanitized)
            
            # Remove template injection patterns
            sanitized = re.sub(r'\{\{.*?\}\}', '', sanitized)
            sanitized = re.sub(r'\{%.*?%\}', '', sanitized)
            sanitized = re.sub(r'\$\{.*?\}', '', sanitized)
            
            # Remove excessive whitespace and control characters
            sanitized = ' '.join(sanitized.split())
            sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in ['\n', '\t'])
            
            # Limit length after sanitization
            if len(sanitized) > self.max_prompt_length:
                sanitized = sanitized[:self.max_prompt_length] + '...'
            
            return sanitized
            
        except Exception as e:
            logger.error(f"Error sanitizing prompt: {e}")
            return prompt[:100]  # Return truncated original on error
    
    def _analyze_content(self, prompt: str) -> Dict[str, Any]:
        """Analyze prompt content for trading relevance and suspicious patterns"""
        try:
            words = prompt.lower().split()
            total_words = len(words)
            
            if total_words == 0:
                return {
                    'trading_relevance': 0.0,
                    'suspicious_score': 1.0,
                    'analysis': 'Empty content'
                }
            
            # Count trading-related keywords
            trading_word_count = sum(1 for word in words if word in self.trading_keywords)
            trading_relevance = trading_word_count / total_words if total_words > 0 else 0
            
            # Suspicious indicators
            suspicious_indicators = 0
            
            # Too many special characters
            special_char_ratio = sum(1 for char in prompt if not char.isalnum() and char not in ' .,!?-') / len(prompt)
            if special_char_ratio > 0.3:
                suspicious_indicators += 1
            
            # Too many uppercase letters
            upper_ratio = sum(1 for char in prompt if char.isupper()) / len(prompt)
            if upper_ratio > 0.5:
                suspicious_indicators += 1
            
            # Repeated patterns
            if len(set(words)) < len(words) * 0.3:  # Too many repeated words
                suspicious_indicators += 1
            
            # Very long words (potential encoding)
            long_words = [word for word in words if len(word) > 20]
            if len(long_words) > 2:
                suspicious_indicators += 1
            
            suspicious_score = suspicious_indicators / 4  # Normalize to 0-1
            
            return {
                'trading_relevance': trading_relevance,
                'suspicious_score': suspicious_score,
                'total_words': total_words,
                'trading_words': trading_word_count,
                'special_char_ratio': special_char_ratio,
                'long_words_count': len(long_words),
                'analysis': 'Content analysis complete'
            }
            
        except Exception as e:
            logger.error(f"Error analyzing content: {e}")
            return {
                'trading_relevance': 0.0,
                'suspicious_score': 1.0,
                'analysis': f'Analysis error: {e}'
            }

# Global prompt injection protector instance
prompt_protector = PromptInjectionProtector()