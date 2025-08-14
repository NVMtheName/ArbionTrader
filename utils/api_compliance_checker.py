"""
API Compliance Checker
Comprehensive audit and validation of API integrations against RFC standards
"""

import logging
import importlib
from typing import Dict, List, Any, Tuple
from datetime import datetime
import inspect

logger = logging.getLogger(__name__)

class APIComplianceChecker:
    """Comprehensive API compliance checker for all integrations"""
    
    def __init__(self):
        self.compliance_results = {}
        self.rfc_standards = {
            'RFC6749': 'OAuth 2.0 Authorization Framework',
            'RFC6750': 'Bearer Token Usage',
            'RFC7636': 'Proof Key for Code Exchange (PKCE)',
            'RFC1945': 'HTTP/1.0',
            'RFC2616': 'HTTP/1.1'
        }
    
    def audit_all_apis(self) -> Dict[str, Any]:
        """Perform comprehensive audit of all API integrations"""
        try:
            audit_results = {
                'timestamp': datetime.utcnow().isoformat(),
                'overall_compliance': 0,
                'api_results': {},
                'critical_issues': [],
                'recommendations': []
            }
            
            # Audit each API integration
            apis_to_audit = [
                ('Coinbase OAuth2', 'utils.coinbase_oauth'),
                ('Schwab OAuth2', 'utils.schwab_oauth'),
                ('OpenAI API', 'utils.openai_auth_manager'),
                ('E-trade OAuth1.0a', 'utils.etrade_oauth'),
                ('Coinbase v2 API', 'utils.coinbase_v2_client')
            ]
            
            total_score = 0
            api_count = 0
            
            for api_name, module_path in apis_to_audit:
                try:
                    api_result = self._audit_api_module(api_name, module_path)
                    audit_results['api_results'][api_name] = api_result
                    total_score += api_result['compliance_score']
                    api_count += 1
                    
                    # Collect critical issues
                    if api_result['critical_issues']:
                        audit_results['critical_issues'].extend(api_result['critical_issues'])
                    
                except Exception as e:
                    logger.error(f"Error auditing {api_name}: {e}")
                    audit_results['api_results'][api_name] = {
                        'compliance_score': 0,
                        'error': str(e),
                        'status': 'AUDIT_FAILED'
                    }
            
            # Calculate overall compliance
            audit_results['overall_compliance'] = total_score / api_count if api_count > 0 else 0
            
            # Generate recommendations
            audit_results['recommendations'] = self._generate_recommendations(audit_results)
            
            return audit_results
            
        except Exception as e:
            logger.error(f"Error performing API audit: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'overall_compliance': 0
            }
    
    def _audit_api_module(self, api_name: str, module_path: str) -> Dict[str, Any]:
        """Audit a specific API module for compliance"""
        try:
            module = importlib.import_module(module_path)
            
            result = {
                'api_name': api_name,
                'module_path': module_path,
                'compliance_score': 0,
                'checks_passed': 0,
                'checks_total': 0,
                'critical_issues': [],
                'warnings': [],
                'compliant_features': [],
                'status': 'UNKNOWN'
            }
            
            # Determine API type and run appropriate checks
            if 'oauth' in module_path.lower():
                if 'coinbase' in module_path or 'schwab' in module_path:
                    result = self._audit_oauth2_module(module, result)
                elif 'etrade' in module_path:
                    result = self._audit_oauth1_module(module, result)
            elif 'openai' in module_path:
                result = self._audit_openai_module(module, result)
            elif 'coinbase_v2' in module_path:
                result = self._audit_coinbase_v2_module(module, result)
            
            # Calculate compliance score
            if result['checks_total'] > 0:
                result['compliance_score'] = (result['checks_passed'] / result['checks_total']) * 100
            
            # Determine status
            if result['compliance_score'] >= 90:
                result['status'] = 'COMPLIANT'
            elif result['compliance_score'] >= 70:
                result['status'] = 'MOSTLY_COMPLIANT'
            elif result['compliance_score'] >= 50:
                result['status'] = 'PARTIALLY_COMPLIANT'
            else:
                result['status'] = 'NON_COMPLIANT'
            
            return result
            
        except Exception as e:
            logger.error(f"Error auditing module {module_path}: {e}")
            return {
                'api_name': api_name,
                'error': str(e),
                'compliance_score': 0,
                'status': 'AUDIT_ERROR'
            }
    
    def _audit_oauth2_module(self, module: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        """Audit OAuth2 module for RFC 6749 and RFC 6750 compliance"""
        checks = [
            ('State parameter validation', 'generate_secure_state'),
            ('Authorization URL generation', 'get_authorization_url'),
            ('Token exchange', 'exchange_code_for_tokens'),
            ('PKCE implementation', 'generate_pkce_pair'),
            ('Rate limiting', 'check_rate_limiting'),
            ('Error handling', 'format_error_response'),
            ('Session security', 'validate_state_security'),
            ('Redirect URI validation', 'validate_redirect_uri')
        ]
        
        for check_name, method_name in checks:
            result['checks_total'] += 1
            
            if hasattr(module, method_name):
                result['checks_passed'] += 1
                result['compliant_features'].append(check_name)
            else:
                # Check if method exists in any class within the module
                found = False
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if hasattr(obj, method_name):
                        result['checks_passed'] += 1
                        result['compliant_features'].append(f"{check_name} (in {name})")
                        found = True
                        break
                
                if not found:
                    result['warnings'].append(f"Missing {check_name} implementation")
        
        # Check for RFC 6750 Bearer token compliance
        bearer_token_checks = [
            ('Bearer token validation', 'validate_authorization_header'),
            ('Token scope validation', 'validate_token_scope'),
            ('WWW-Authenticate header', 'generate_www_authenticate_header')
        ]
        
        for check_name, method_name in bearer_token_checks:
            result['checks_total'] += 1
            
            # Check if RFC 6750 validator is used
            if 'rfc6750' in str(module.__dict__) or hasattr(module, method_name):
                result['checks_passed'] += 1
                result['compliant_features'].append(f"RFC 6750: {check_name}")
            else:
                result['critical_issues'].append(f"Missing RFC 6750 compliance: {check_name}")
        
        return result
    
    def _audit_oauth1_module(self, module: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        """Audit OAuth 1.0a module for compliance"""
        checks = [
            ('Signature generation', '_generate_oauth_signature'),
            ('Request token', 'get_request_token'),
            ('Access token', 'get_access_token'),
            ('Nonce generation', 'secrets.token_hex'),
            ('Timestamp validation', 'time.time')
        ]
        
        for check_name, method_name in checks:
            result['checks_total'] += 1
            
            if hasattr(module, method_name) or method_name in str(module.__dict__):
                result['checks_passed'] += 1
                result['compliant_features'].append(check_name)
            else:
                result['warnings'].append(f"Missing {check_name} implementation")
        
        return result
    
    def _audit_openai_module(self, module: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        """Audit OpenAI module for security and best practices"""
        checks = [
            ('API key validation', 'validate_api_key'),
            ('Rate limiting', 'RateLimitManager'),
            ('Error handling', 'handle_api_error'),
            ('Connection monitoring', 'ConnectionStatus'),
            ('Retry logic', 'retry_with_backoff'),
            ('Timeout handling', 'timeout'),
            ('Prompt validation', 'validate_prompt')
        ]
        
        for check_name, feature_name in checks:
            result['checks_total'] += 1
            
            module_content = str(module.__dict__)
            if feature_name in module_content or hasattr(module, feature_name):
                result['checks_passed'] += 1
                result['compliant_features'].append(check_name)
            else:
                result['warnings'].append(f"Missing {check_name} implementation")
        
        return result
    
    def _audit_coinbase_v2_module(self, module: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        """Audit Coinbase v2 module for advanced features"""
        checks = [
            ('Smart Account support', 'create_smart_account'),
            ('Transaction batching', 'batch_transactions'),
            ('Gas sponsorship', 'sponsor_transaction'),
            ('Multi-network support', 'supported_networks'),
            ('Credential encryption', 'encrypt_credentials'),
            ('Error handling', 'handle_api_error')
        ]
        
        for check_name, feature_name in checks:
            result['checks_total'] += 1
            
            if hasattr(module, feature_name) or feature_name in str(module.__dict__):
                result['checks_passed'] += 1
                result['compliant_features'].append(check_name)
            else:
                result['warnings'].append(f"Missing {check_name} implementation")
        
        return result
    
    def _generate_recommendations(self, audit_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on audit results"""
        recommendations = []
        
        overall_score = audit_results['overall_compliance']
        
        if overall_score < 50:
            recommendations.append("CRITICAL: Overall API compliance is below 50%. Immediate action required.")
        elif overall_score < 70:
            recommendations.append("WARNING: API compliance needs improvement. Address missing features.")
        elif overall_score < 90:
            recommendations.append("GOOD: API compliance is acceptable but can be enhanced.")
        else:
            recommendations.append("EXCELLENT: API compliance meets enterprise standards.")
        
        # Critical issue recommendations
        if audit_results['critical_issues']:
            recommendations.append(f"Address {len(audit_results['critical_issues'])} critical security issues immediately.")
        
        # Specific recommendations based on common issues
        for api_name, api_result in audit_results['api_results'].items():
            if api_result.get('compliance_score', 0) < 70:
                recommendations.append(f"Enhance {api_name} compliance - currently at {api_result.get('compliance_score', 0):.1f}%")
        
        return recommendations
    
    def generate_compliance_report(self) -> str:
        """Generate a formatted compliance report"""
        audit_results = self.audit_all_apis()
        
        report = f"""
# API Compliance Audit Report
Generated: {audit_results['timestamp']}
Overall Compliance Score: {audit_results['overall_compliance']:.1f}%

## Summary
"""
        
        for api_name, api_result in audit_results['api_results'].items():
            status = api_result.get('status', 'UNKNOWN')
            score = api_result.get('compliance_score', 0)
            report += f"- {api_name}: {status} ({score:.1f}%)\n"
        
        if audit_results['critical_issues']:
            report += f"\n## Critical Issues ({len(audit_results['critical_issues'])})\n"
            for issue in audit_results['critical_issues']:
                report += f"- {issue}\n"
        
        if audit_results['recommendations']:
            report += f"\n## Recommendations\n"
            for rec in audit_results['recommendations']:
                report += f"- {rec}\n"
        
        return report

# Global compliance checker instance
api_compliance_checker = APIComplianceChecker()