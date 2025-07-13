"""
REST API Endpoints for OpenAI Codex GitHub Integration
Provides HTTP endpoints for programmatic access to GitHub repositories
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from utils.codex_backend_api import CodexBackendAPI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app for API endpoints
api_app = Flask(__name__)
CORS(api_app)  # Enable CORS for external access

# Initialize backend API
codex_api = CodexBackendAPI()

@api_app.route('/api/codex/repositories', methods=['GET'])
def get_repositories():
    """Get list of accessible repositories"""
    try:
        org = request.args.get('org')
        repos = codex_api.list_repositories(org)
        
        return jsonify({
            'success': True,
            'repositories': repos,
            'count': len(repos)
        })
        
    except Exception as e:
        logger.error(f"Repository listing failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_app.route('/api/codex/repository/<owner>/<repo>/files', methods=['GET'])
def get_repository_files(owner, repo):
    """Get repository file structure"""
    try:
        path = request.args.get('path', '')
        files = codex_api.get_repository_files(owner, repo, path)
        
        return jsonify({
            'success': True,
            'owner': owner,
            'repo': repo,
            'path': path,
            'files': files
        })
        
    except Exception as e:
        logger.error(f"File listing failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_app.route('/api/codex/repository/<owner>/<repo>/file', methods=['GET'])
def read_file(owner, repo):
    """Read a file from repository"""
    try:
        file_path = request.args.get('path')
        if not file_path:
            return jsonify({
                'success': False,
                'error': 'File path parameter is required'
            }), 400
        
        result = codex_api.read_file(owner, repo, file_path)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"File reading failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_app.route('/api/codex/repository/<owner>/<repo>/file', methods=['POST'])
def write_file(owner, repo):
    """Write/update a file in repository"""
    try:
        data = request.get_json()
        
        file_path = data.get('path')
        content = data.get('content')
        commit_message = data.get('commit_message')
        sha = data.get('sha')
        
        if not file_path or content is None:
            return jsonify({
                'success': False,
                'error': 'File path and content are required'
            }), 400
        
        result = codex_api.write_file(owner, repo, file_path, content, commit_message, sha)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"File writing failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_app.route('/api/codex/analyze', methods=['POST'])
def analyze_code():
    """Analyze code using OpenAI Codex"""
    try:
        data = request.get_json()
        
        code = data.get('code')
        language = data.get('language', 'python')
        
        if not code:
            return jsonify({
                'success': False,
                'error': 'Code is required'
            }), 400
        
        result = codex_api.analyze_code(code, language)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Code analysis failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_app.route('/api/codex/improve', methods=['POST'])
def improve_code():
    """Improve code using OpenAI Codex"""
    try:
        data = request.get_json()
        
        code = data.get('code')
        requirements = data.get('requirements')
        language = data.get('language', 'python')
        
        if not code or not requirements:
            return jsonify({
                'success': False,
                'error': 'Code and requirements are required'
            }), 400
        
        result = codex_api.improve_code(code, requirements, language)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Code improvement failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_app.route('/api/codex/repository/<owner>/<repo>/refactor', methods=['POST'])
def refactor_file(owner, repo):
    """Refactor a file using OpenAI Codex"""
    try:
        data = request.get_json()
        
        file_path = data.get('file_path')
        goals = data.get('refactoring_goals')
        
        if not file_path or not goals:
            return jsonify({
                'success': False,
                'error': 'File path and refactoring goals are required'
            }), 400
        
        result = codex_api.refactor_file(owner, repo, file_path, goals)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"File refactoring failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_app.route('/api/codex/repository/<owner>/<repo>/summary', methods=['GET'])
def get_repository_summary(owner, repo):
    """Get comprehensive repository summary"""
    try:
        result = codex_api.get_repository_summary(owner, repo)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Repository summary failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_app.route('/api/codex/bulk-operations', methods=['POST'])
def bulk_operations():
    """Perform bulk file operations"""
    try:
        data = request.get_json()
        
        owner = data.get('owner')
        repo = data.get('repo')
        operations = data.get('operations', [])
        
        if not owner or not repo or not operations:
            return jsonify({
                'success': False,
                'error': 'Owner, repo, and operations are required'
            }), 400
        
        result = codex_api.bulk_file_operations(owner, repo, operations)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Bulk operations failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_app.route('/api/codex/status', methods=['GET'])
def api_status():
    """Check API status and configuration"""
    try:
        # Check if GitHub and OpenAI credentials are configured
        github_configured = bool(codex_api.github_integration.github_token)
        openai_configured = bool(codex_api.github_integration.openai_client)
        
        return jsonify({
            'success': True,
            'status': 'operational',
            'github_configured': github_configured,
            'openai_configured': openai_configured,
            'version': '1.0.0',
            'endpoints': [
                'GET /api/codex/repositories',
                'GET /api/codex/repository/<owner>/<repo>/files',
                'GET /api/codex/repository/<owner>/<repo>/file',
                'POST /api/codex/repository/<owner>/<repo>/file',
                'POST /api/codex/analyze',
                'POST /api/codex/improve',
                'POST /api/codex/repository/<owner>/<repo>/refactor',
                'GET /api/codex/repository/<owner>/<repo>/summary',
                'POST /api/codex/bulk-operations'
            ]
        })
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_app.route('/api/codex/configure', methods=['POST'])
def configure_credentials():
    """Configure GitHub and OpenAI credentials"""
    try:
        data = request.get_json()
        
        github_token = data.get('github_token')
        openai_api_key = data.get('openai_api_key')
        
        if not github_token or not openai_api_key:
            return jsonify({
                'success': False,
                'error': 'GitHub token and OpenAI API key are required'
            }), 400
        
        # Update credentials
        codex_api.github_integration.set_credentials(github_token, openai_api_key)
        
        return jsonify({
            'success': True,
            'message': 'Credentials configured successfully'
        })
        
    except Exception as e:
        logger.error(f"Credential configuration failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Run the API server
    port = int(os.environ.get('CODEX_API_PORT', 5001))
    api_app.run(host='0.0.0.0', port=port, debug=True)