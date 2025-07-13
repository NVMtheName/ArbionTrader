"""
GitHub Codex Integration Routes
Provides web interface for GitHub repository management and AI-powered code editing
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
import logging
import json

from utils.github_codex_integration import GitHubCodexIntegration

logger = logging.getLogger(__name__)

github_bp = Blueprint('github', __name__, url_prefix='/github')

@github_bp.route('/setup', methods=['GET', 'POST'])
@login_required
def github_setup():
    """GitHub integration setup page"""
    if request.method == 'POST':
        try:
            github_token = request.form.get('github_token')
            
            if not github_token:
                flash('GitHub token is required', 'error')
                return redirect(url_for('github.github_setup'))
            
            # Initialize GitHub integration
            github_integration = GitHubCodexIntegration(user_id=current_user.id)
            
            # Save credentials
            success = github_integration.save_github_credentials(current_user.id, github_token)
            
            if success:
                flash('GitHub credentials saved successfully!', 'success')
                return redirect(url_for('github.repositories'))
            else:
                flash('Failed to save GitHub credentials', 'error')
                
        except Exception as e:
            logger.error(f"GitHub setup error: {e}")
            flash(f'Setup failed: {str(e)}', 'error')
    
    return render_template('github/setup.html')

@github_bp.route('/repositories')
@login_required
def repositories():
    """List user's GitHub repositories"""
    try:
        github_integration = GitHubCodexIntegration(user_id=current_user.id)
        repos = github_integration.list_repositories()
        
        return render_template('github/repositories.html', repositories=repos)
        
    except Exception as e:
        logger.error(f"Failed to load repositories: {e}")
        flash(f'Failed to load repositories: {str(e)}', 'error')
        return redirect(url_for('github.github_setup'))

@github_bp.route('/repository/<owner>/<repo>')
@login_required
def repository_details(owner, repo):
    """Show repository details and file structure"""
    try:
        github_integration = GitHubCodexIntegration(user_id=current_user.id)
        structure = github_integration.get_repository_structure(owner, repo)
        
        return render_template('github/repository_details.html', 
                             owner=owner, repo=repo, structure=structure)
        
    except Exception as e:
        logger.error(f"Failed to load repository details: {e}")
        flash(f'Failed to load repository: {str(e)}', 'error')
        return redirect(url_for('github.repositories'))

@github_bp.route('/editor/<owner>/<repo>')
@login_required
def code_editor(owner, repo):
    """AI-powered code editor interface"""
    try:
        file_path = request.args.get('file', '')
        
        github_integration = GitHubCodexIntegration(user_id=current_user.id)
        
        content = ""
        sha = ""
        
        if file_path:
            content, sha = github_integration.get_file_content(owner, repo, file_path)
        
        return render_template('github/code_editor.html', 
                             owner=owner, repo=repo, file_path=file_path,
                             content=content, sha=sha)
        
    except Exception as e:
        logger.error(f"Failed to load code editor: {e}")
        flash(f'Failed to load editor: {str(e)}', 'error')
        return redirect(url_for('github.repositories'))

@github_bp.route('/api/analyze-code', methods=['POST'])
@login_required
def analyze_code():
    """API endpoint for code analysis"""
    try:
        data = request.get_json()
        code = data.get('code', '')
        language = data.get('language', 'python')
        
        if not code:
            return jsonify({'error': 'No code provided'}), 400
        
        github_integration = GitHubCodexIntegration(user_id=current_user.id)
        analysis = github_integration.analyze_code_with_codex(code, language)
        
        return jsonify(analysis)
        
    except Exception as e:
        logger.error(f"Code analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@github_bp.route('/api/improve-code', methods=['POST'])
@login_required
def improve_code():
    """API endpoint for code improvement"""
    try:
        data = request.get_json()
        code = data.get('code', '')
        requirements = data.get('requirements', '')
        language = data.get('language', 'python')
        
        if not code or not requirements:
            return jsonify({'error': 'Code and requirements are required'}), 400
        
        github_integration = GitHubCodexIntegration(user_id=current_user.id)
        improved_code = github_integration.generate_code_improvements(code, requirements, language)
        
        return jsonify({'improved_code': improved_code})
        
    except Exception as e:
        logger.error(f"Code improvement error: {e}")
        return jsonify({'error': str(e)}), 500

@github_bp.route('/api/commit-changes', methods=['POST'])
@login_required
def commit_changes():
    """API endpoint for committing code changes"""
    try:
        data = request.get_json()
        owner = data.get('owner')
        repo = data.get('repo')
        file_path = data.get('file_path')
        content = data.get('content')
        sha = data.get('sha')
        commit_message = data.get('commit_message', 'AI-powered code update')
        branch = data.get('branch', 'main')
        
        if not all([owner, repo, file_path, content, sha]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        github_integration = GitHubCodexIntegration(user_id=current_user.id)
        success = github_integration.commit_file_changes(
            owner, repo, file_path, content, sha, commit_message, branch
        )
        
        return jsonify({'success': success})
        
    except Exception as e:
        logger.error(f"Commit changes error: {e}")
        return jsonify({'error': str(e)}), 500

@github_bp.route('/api/refactor', methods=['POST'])
@login_required
def intelligent_refactor():
    """API endpoint for intelligent code refactoring"""
    try:
        data = request.get_json()
        owner = data.get('owner')
        repo = data.get('repo')
        file_path = data.get('file_path')
        refactoring_goals = data.get('refactoring_goals')
        
        if not all([owner, repo, file_path, refactoring_goals]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        github_integration = GitHubCodexIntegration(user_id=current_user.id)
        result = github_integration.intelligent_refactoring(
            owner, repo, file_path, refactoring_goals
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Intelligent refactoring error: {e}")
        return jsonify({'error': str(e)}), 500

@github_bp.route('/api/code-review/<owner>/<repo>/<int:pr_number>')
@login_required
def automated_code_review(owner, repo, pr_number):
    """API endpoint for automated code review"""
    try:
        github_integration = GitHubCodexIntegration(user_id=current_user.id)
        review_result = github_integration.automated_code_review(owner, repo, pr_number)
        
        return jsonify(review_result)
        
    except Exception as e:
        logger.error(f"Automated code review error: {e}")
        return jsonify({'error': str(e)}), 500

@github_bp.route('/pull-requests/<owner>/<repo>')
@login_required
def pull_requests(owner, repo):
    """List pull requests for a repository"""
    try:
        github_integration = GitHubCodexIntegration(user_id=current_user.id)
        
        # Get pull requests from GitHub API
        headers = {
            'Authorization': f'token {github_integration.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        import requests
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        pull_requests = response.json()
        
        return render_template('github/pull_requests.html', 
                             owner=owner, repo=repo, pull_requests=pull_requests)
        
    except Exception as e:
        logger.error(f"Failed to load pull requests: {e}")
        flash(f'Failed to load pull requests: {str(e)}', 'error')
        return redirect(url_for('github.repository_details', owner=owner, repo=repo))