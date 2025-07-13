"""
Backend API for OpenAI Codex GitHub Integration
Provides direct programmatic access to GitHub repositories for AI code editing
"""

import os
import logging
import json
from typing import Dict, List, Optional, Any
from utils.github_codex_integration import GitHubCodexIntegration

logger = logging.getLogger(__name__)

class CodexBackendAPI:
    """
    Direct backend API for OpenAI Codex to access and modify GitHub repositories
    Provides programmatic interface without web UI dependencies
    """
    
    def __init__(self, github_token: str = None, openai_api_key: str = None):
        """
        Initialize the backend API with direct credentials
        
        Args:
            github_token: GitHub personal access token
            openai_api_key: OpenAI API key for Codex
        """
        self.github_integration = GitHubCodexIntegration()
        
        # Set credentials directly or load from environment
        if github_token and openai_api_key:
            self.github_integration.set_credentials(github_token, openai_api_key)
        else:
            # Load from environment variables
            github_token = os.environ.get('GITHUB_TOKEN')
            openai_api_key = os.environ.get('OPENAI_API_KEY')
            
            if github_token and openai_api_key:
                self.github_integration.set_credentials(github_token, openai_api_key)
            else:
                logger.warning("GitHub token and OpenAI API key not provided. Some features may not work.")
    
    def list_repositories(self, org: str = None) -> List[Dict]:
        """
        List all repositories accessible to the authenticated user
        
        Args:
            org: Optional organization name to filter repositories
            
        Returns:
            List of repository dictionaries with metadata
        """
        try:
            repos = self.github_integration.list_repositories(org)
            
            # Return simplified repository info for Codex
            simplified_repos = []
            for repo in repos:
                simplified_repos.append({
                    'name': repo.get('name'),
                    'full_name': repo.get('full_name'),
                    'owner': repo.get('owner', {}).get('login'),
                    'language': repo.get('language'),
                    'description': repo.get('description'),
                    'private': repo.get('private'),
                    'clone_url': repo.get('clone_url'),
                    'default_branch': repo.get('default_branch', 'main')
                })
            
            logger.info(f"Retrieved {len(simplified_repos)} repositories")
            return simplified_repos
            
        except Exception as e:
            logger.error(f"Failed to list repositories: {e}")
            return []
    
    def get_repository_files(self, owner: str, repo: str, path: str = "") -> List[Dict]:
        """
        Get file structure of a repository
        
        Args:
            owner: Repository owner
            repo: Repository name  
            path: Optional path to explore (default: root)
            
        Returns:
            List of files and directories
        """
        try:
            structure = self.github_integration.get_repository_structure(owner, repo, path)
            
            if isinstance(structure, list):
                return structure
            elif isinstance(structure, dict):
                return [structure]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to get repository structure: {e}")
            return []
    
    def read_file(self, owner: str, repo: str, file_path: str) -> Dict:
        """
        Read a file from GitHub repository
        
        Args:
            owner: Repository owner
            repo: Repository name
            file_path: Path to the file
            
        Returns:
            Dictionary with file content and metadata
        """
        try:
            content, sha = self.github_integration.get_file_content(owner, repo, file_path)
            
            return {
                'path': file_path,
                'content': content,
                'sha': sha,
                'size': len(content.encode('utf-8')),
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return {
                'path': file_path,
                'content': '',
                'sha': '',
                'size': 0,
                'success': False,
                'error': str(e)
            }
    
    def write_file(self, owner: str, repo: str, file_path: str, content: str, 
                   commit_message: str = None, sha: str = None) -> Dict:
        """
        Write/update a file in GitHub repository
        
        Args:
            owner: Repository owner
            repo: Repository name
            file_path: Path to the file
            content: New file content
            commit_message: Optional commit message
            sha: File SHA for updates (required for existing files)
            
        Returns:
            Dictionary with operation result
        """
        try:
            # Generate commit message if not provided
            if not commit_message:
                commit_message = f"Update {file_path} via Codex API"
            
            # If SHA not provided, try to get it
            if not sha:
                try:
                    _, sha = self.github_integration.get_file_content(owner, repo, file_path)
                except:
                    # File doesn't exist, create new
                    sha = ""
            
            success = self.github_integration.commit_file_changes(
                owner, repo, file_path, content, sha, commit_message
            )
            
            return {
                'path': file_path,
                'success': success,
                'commit_message': commit_message,
                'operation': 'update' if sha else 'create'
            }
            
        except Exception as e:
            logger.error(f"Failed to write file {file_path}: {e}")
            return {
                'path': file_path,
                'success': False,
                'error': str(e)
            }
    
    def analyze_code(self, code: str, language: str = "python") -> Dict:
        """
        Analyze code using OpenAI Codex
        
        Args:
            code: Source code to analyze
            language: Programming language
            
        Returns:
            Analysis results
        """
        try:
            analysis = self.github_integration.analyze_code_with_codex(code, language)
            return {
                'success': True,
                'analysis': analysis,
                'language': language
            }
            
        except Exception as e:
            logger.error(f"Code analysis failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def improve_code(self, code: str, requirements: str, language: str = "python") -> Dict:
        """
        Generate code improvements using OpenAI Codex
        
        Args:
            code: Original source code
            requirements: Improvement requirements
            language: Programming language
            
        Returns:
            Improved code
        """
        try:
            improved_code = self.github_integration.generate_code_improvements(
                code, requirements, language
            )
            
            return {
                'success': True,
                'original_code': code,
                'improved_code': improved_code,
                'requirements': requirements,
                'language': language
            }
            
        except Exception as e:
            logger.error(f"Code improvement failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def refactor_file(self, owner: str, repo: str, file_path: str, 
                     refactoring_goals: str) -> Dict:
        """
        Intelligently refactor a file using OpenAI Codex
        
        Args:
            owner: Repository owner
            repo: Repository name
            file_path: Path to file to refactor
            refactoring_goals: Description of refactoring goals
            
        Returns:
            Refactoring results
        """
        try:
            result = self.github_integration.intelligent_refactoring(
                owner, repo, file_path, refactoring_goals
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Refactoring failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_pull_request(self, owner: str, repo: str, title: str, 
                           body: str, head: str, base: str = "main") -> Dict:
        """
        Create a pull request for code changes
        
        Args:
            owner: Repository owner
            repo: Repository name
            title: PR title
            body: PR description
            head: Source branch
            base: Target branch
            
        Returns:
            Pull request information
        """
        try:
            pr_data = self.github_integration.create_pull_request(
                owner, repo, title, body, head, base
            )
            
            return {
                'success': True,
                'pull_request': pr_data,
                'url': pr_data.get('html_url'),
                'number': pr_data.get('number')
            }
            
        except Exception as e:
            logger.error(f"PR creation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def bulk_file_operations(self, owner: str, repo: str, operations: List[Dict]) -> Dict:
        """
        Perform bulk file operations (read/write/analyze)
        
        Args:
            owner: Repository owner
            repo: Repository name
            operations: List of operation dictionaries
            
        Returns:
            Results of all operations
        """
        results = []
        
        for op in operations:
            operation_type = op.get('type')
            file_path = op.get('file_path')
            
            try:
                if operation_type == 'read':
                    result = self.read_file(owner, repo, file_path)
                    
                elif operation_type == 'write':
                    result = self.write_file(
                        owner, repo, file_path, 
                        op.get('content', ''),
                        op.get('commit_message'),
                        op.get('sha')
                    )
                    
                elif operation_type == 'analyze':
                    file_data = self.read_file(owner, repo, file_path)
                    if file_data['success']:
                        result = self.analyze_code(
                            file_data['content'],
                            op.get('language', 'python')
                        )
                        result['file_path'] = file_path
                    else:
                        result = {'success': False, 'error': 'Failed to read file'}
                        
                elif operation_type == 'improve':
                    file_data = self.read_file(owner, repo, file_path)
                    if file_data['success']:
                        result = self.improve_code(
                            file_data['content'],
                            op.get('requirements', ''),
                            op.get('language', 'python')
                        )
                        result['file_path'] = file_path
                    else:
                        result = {'success': False, 'error': 'Failed to read file'}
                        
                else:
                    result = {'success': False, 'error': f'Unknown operation: {operation_type}'}
                
                result['operation'] = operation_type
                results.append(result)
                
            except Exception as e:
                results.append({
                    'operation': operation_type,
                    'file_path': file_path,
                    'success': False,
                    'error': str(e)
                })
        
        return {
            'total_operations': len(operations),
            'successful_operations': sum(1 for r in results if r.get('success')),
            'failed_operations': sum(1 for r in results if not r.get('success')),
            'results': results
        }
    
    def get_repository_summary(self, owner: str, repo: str) -> Dict:
        """
        Get comprehensive repository summary for Codex
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Complete repository analysis
        """
        try:
            # Get repository structure
            structure = self.get_repository_files(owner, repo)
            
            # Analyze key files
            key_files = []
            for item in structure:
                if item.get('type') == 'file':
                    name = item.get('name', '')
                    if (name.endswith('.py') or name.endswith('.js') or 
                        name.endswith('.md') or name in ['README.md', 'requirements.txt', 'package.json']):
                        file_data = self.read_file(owner, repo, item.get('path', ''))
                        if file_data['success']:
                            key_files.append({
                                'path': item.get('path'),
                                'name': name,
                                'size': file_data['size'],
                                'content_preview': file_data['content'][:500] + '...' if len(file_data['content']) > 500 else file_data['content']
                            })
            
            return {
                'owner': owner,
                'repo': repo,
                'structure': structure,
                'key_files': key_files,
                'file_count': len([f for f in structure if f.get('type') == 'file']),
                'directory_count': len([f for f in structure if f.get('type') == 'dir']),
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Repository summary failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# Global instance for easy access
codex_backend = CodexBackendAPI()

# Direct function interfaces for Codex
def codex_list_repos(org: str = None) -> List[Dict]:
    """Direct interface: List repositories"""
    return codex_backend.list_repositories(org)

def codex_read_file(owner: str, repo: str, file_path: str) -> Dict:
    """Direct interface: Read file"""
    return codex_backend.read_file(owner, repo, file_path)

def codex_write_file(owner: str, repo: str, file_path: str, content: str, 
                     commit_message: str = None) -> Dict:
    """Direct interface: Write file"""
    return codex_backend.write_file(owner, repo, file_path, content, commit_message)

def codex_analyze_code(code: str, language: str = "python") -> Dict:
    """Direct interface: Analyze code"""
    return codex_backend.analyze_code(code, language)

def codex_improve_code(code: str, requirements: str, language: str = "python") -> Dict:
    """Direct interface: Improve code"""
    return codex_backend.improve_code(code, requirements, language)

def codex_refactor_file(owner: str, repo: str, file_path: str, goals: str) -> Dict:
    """Direct interface: Refactor file"""
    return codex_backend.refactor_file(owner, repo, file_path, goals)

def codex_repo_summary(owner: str, repo: str) -> Dict:
    """Direct interface: Get repository summary"""
    return codex_backend.get_repository_summary(owner, repo)