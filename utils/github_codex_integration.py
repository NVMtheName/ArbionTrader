"""
GitHub Integration with OpenAI Codex for Backend Code Editing
This module provides AI-powered code editing capabilities through GitHub integration
"""

import os
import logging
import requests
import base64
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from openai import OpenAI

logger = logging.getLogger(__name__)

class GitHubCodexIntegration:
    """
    GitHub integration with OpenAI Codex for intelligent code editing
    Supports repository analysis, code modification, and automated commits
    """
    
    def __init__(self, user_id: int = None):
        self.user_id = user_id
        self.github_token = None
        self.openai_client = None
        self.github_api_base = "https://api.github.com"
        
        # Load credentials from user's stored API credentials
        if user_id:
            self._load_credentials()
    
    def _load_credentials(self):
        """Load GitHub and OpenAI credentials from user's stored API credentials"""
        try:
            from models import APICredential
            from utils.encryption import decrypt_credentials
            
            # Load GitHub credentials
            github_cred = APICredential.query.filter_by(
                user_id=self.user_id,
                provider='github',
                is_active=True
            ).first()
            
            if github_cred:
                github_data = decrypt_credentials(github_cred.encrypted_credentials)
                self.github_token = github_data.get('token')
                logger.info(f"GitHub credentials loaded for user {self.user_id}")
            
            # Load OpenAI credentials
            openai_cred = APICredential.query.filter_by(
                user_id=self.user_id,
                provider='openai',
                is_active=True
            ).first()
            
            if openai_cred:
                openai_data = decrypt_credentials(openai_cred.encrypted_credentials)
                api_key = openai_data.get('api_key')
                if api_key:
                    # the newest OpenAI model is "gpt-5.2" which is the current model.
                    # do not change this unless explicitly requested by the user
                    self.openai_client = OpenAI(api_key=api_key)
                    logger.info(f"OpenAI Codex credentials loaded for user {self.user_id}")
            
        except Exception as e:
            logger.error(f"Failed to load credentials for user {self.user_id}: {e}")
    
    def set_credentials(self, github_token: str, openai_api_key: str):
        """Set credentials programmatically"""
        self.github_token = github_token
        # the newest OpenAI model is "gpt-5.2" which is the current model.
        # do not change this unless explicitly requested by the user
        self.openai_client = OpenAI(api_key=openai_api_key)
    
    def save_github_credentials(self, user_id: int, github_token: str):
        """Save GitHub credentials to database"""
        try:
            from models import APICredential
            from utils.encryption import encrypt_credentials
            from app import db
            
            credentials = {'token': github_token}
            encrypted_creds = encrypt_credentials(credentials)
            
            # Check if credentials already exist
            existing_cred = APICredential.query.filter_by(
                user_id=user_id,
                provider='github'
            ).first()
            
            if existing_cred:
                existing_cred.encrypted_credentials = encrypted_creds
                existing_cred.updated_at = datetime.utcnow()
                existing_cred.is_active = True
            else:
                new_cred = APICredential(
                    user_id=user_id,
                    provider='github',
                    encrypted_credentials=encrypted_creds,
                    is_active=True
                )
                db.session.add(new_cred)
            
            db.session.commit()
            logger.info(f"GitHub credentials saved for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save GitHub credentials: {e}")
            return False
    
    def list_repositories(self, org: str = None) -> List[Dict]:
        """List repositories for the authenticated user or organization"""
        try:
            if not self.github_token:
                raise ValueError("GitHub token not configured")
            
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            if org:
                url = f"{self.github_api_base}/orgs/{org}/repos"
            else:
                url = f"{self.github_api_base}/user/repos"
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            repos = response.json()
            logger.info(f"Retrieved {len(repos)} repositories")
            return repos
            
        except Exception as e:
            logger.error(f"Failed to list repositories: {e}")
            return []
    
    def get_repository_structure(self, owner: str, repo: str, path: str = "") -> Dict:
        """Get repository file structure"""
        try:
            if not self.github_token:
                raise ValueError("GitHub token not configured")
            
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            url = f"{self.github_api_base}/repos/{owner}/{repo}/contents/{path}"
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get repository structure: {e}")
            return {}
    
    def get_file_content(self, owner: str, repo: str, path: str) -> Tuple[str, str]:
        """Get file content from GitHub repository"""
        try:
            if not self.github_token:
                raise ValueError("GitHub token not configured")
            
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            url = f"{self.github_api_base}/repos/{owner}/{repo}/contents/{path}"
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            file_data = response.json()
            
            # Decode base64 content
            content = base64.b64decode(file_data['content']).decode('utf-8')
            sha = file_data['sha']
            
            logger.info(f"Retrieved file content for {path}")
            return content, sha
            
        except Exception as e:
            logger.error(f"Failed to get file content: {e}")
            return "", ""
    
    def analyze_code_with_codex(self, code: str, language: str = "python") -> Dict:
        """Analyze code using OpenAI Codex"""
        try:
            if not self.openai_client:
                raise ValueError("OpenAI client not configured")
            
            prompt = f"""
            Analyze the following {language} code and provide:
            1. Code quality assessment
            2. Potential improvements
            3. Security vulnerabilities
            4. Performance optimizations
            5. Best practices recommendations
            
            Code:
            ```{language}
            {code}
            ```
            
            Please provide your analysis in JSON format.
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-5.2",
                messages=[
                    {"role": "system", "content": "You are an expert code reviewer and software architect."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=2000
            )
            
            analysis = json.loads(response.choices[0].message.content)
            logger.info("Code analysis completed successfully")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze code with Codex: {e}")
            return {"error": str(e)}
    
    def generate_code_improvements(self, code: str, requirements: str, language: str = "python") -> str:
        """Generate code improvements using OpenAI Codex"""
        try:
            if not self.openai_client:
                raise ValueError("OpenAI client not configured")
            
            prompt = f"""
            Improve the following {language} code based on these requirements:
            {requirements}
            
            Original code:
            ```{language}
            {code}
            ```
            
            Please provide the improved code with comments explaining the changes.
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-5.2",
                messages=[
                    {"role": "system", "content": "You are an expert software developer focused on code improvement and optimization."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=3000
            )
            
            improved_code = response.choices[0].message.content
            logger.info("Code improvements generated successfully")
            return improved_code
            
        except Exception as e:
            logger.error(f"Failed to generate code improvements: {e}")
            return f"Error generating improvements: {str(e)}"
    
    def commit_file_changes(self, owner: str, repo: str, path: str, content: str, 
                           sha: str, commit_message: str, branch: str = "main") -> bool:
        """Commit file changes to GitHub repository"""
        try:
            if not self.github_token:
                raise ValueError("GitHub token not configured")
            
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json'
            }
            
            # Encode content to base64
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            
            data = {
                'message': commit_message,
                'content': encoded_content,
                'sha': sha,
                'branch': branch
            }
            
            url = f"{self.github_api_base}/repos/{owner}/{repo}/contents/{path}"
            response = requests.put(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            logger.info(f"Successfully committed changes to {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to commit file changes: {e}")
            return False
    
    def create_pull_request(self, owner: str, repo: str, title: str, body: str,
                           head: str, base: str = "main") -> Dict:
        """Create a pull request with code changes"""
        try:
            if not self.github_token:
                raise ValueError("GitHub token not configured")
            
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json'
            }
            
            data = {
                'title': title,
                'body': body,
                'head': head,
                'base': base
            }
            
            url = f"{self.github_api_base}/repos/{owner}/{repo}/pulls"
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            pr_data = response.json()
            logger.info(f"Created pull request #{pr_data['number']}")
            return pr_data
            
        except Exception as e:
            logger.error(f"Failed to create pull request: {e}")
            return {"error": str(e)}
    
    def automated_code_review(self, owner: str, repo: str, pull_request_number: int) -> Dict:
        """Perform automated code review using OpenAI Codex"""
        try:
            if not self.github_token or not self.openai_client:
                raise ValueError("GitHub or OpenAI credentials not configured")
            
            # Get PR files
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            url = f"{self.github_api_base}/repos/{owner}/{repo}/pulls/{pull_request_number}/files"
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            files = response.json()
            review_comments = []
            
            for file in files:
                if file['status'] in ['added', 'modified'] and file['filename'].endswith('.py'):
                    # Get file content and analyze
                    content, _ = self.get_file_content(owner, repo, file['filename'])
                    if content:
                        analysis = self.analyze_code_with_codex(content, "python")
                        if 'error' not in analysis:
                            review_comments.append({
                                'file': file['filename'],
                                'analysis': analysis
                            })
            
            logger.info(f"Automated code review completed for PR #{pull_request_number}")
            return {
                'pull_request': pull_request_number,
                'reviews': review_comments
            }
            
        except Exception as e:
            logger.error(f"Failed to perform automated code review: {e}")
            return {"error": str(e)}
    
    def intelligent_refactoring(self, owner: str, repo: str, file_path: str, 
                               refactoring_goals: str) -> Dict:
        """Perform intelligent code refactoring using OpenAI Codex"""
        try:
            if not self.github_token or not self.openai_client:
                raise ValueError("GitHub or OpenAI credentials not configured")
            
            # Get current file content
            original_content, sha = self.get_file_content(owner, repo, file_path)
            if not original_content:
                return {"error": "Failed to retrieve file content"}
            
            # Generate refactored code
            refactored_code = self.generate_code_improvements(
                original_content, 
                refactoring_goals, 
                "python"
            )
            
            # Create a new branch for the refactoring
            branch_name = f"refactor-{file_path.replace('/', '-')}-{int(datetime.now().timestamp())}"
            
            # Commit changes to new branch
            success = self.commit_file_changes(
                owner, repo, file_path, refactored_code, sha,
                f"Refactor {file_path}: {refactoring_goals}",
                branch_name
            )
            
            if success:
                # Create pull request
                pr_data = self.create_pull_request(
                    owner, repo,
                    f"Refactor {file_path}",
                    f"Automated refactoring based on: {refactoring_goals}",
                    branch_name
                )
                
                return {
                    "success": True,
                    "branch": branch_name,
                    "pull_request": pr_data,
                    "original_content": original_content,
                    "refactored_content": refactored_code
                }
            else:
                return {"error": "Failed to commit refactored code"}
            
        except Exception as e:
            logger.error(f"Failed to perform intelligent refactoring: {e}")
            return {"error": str(e)}

# Global instance for easy access
github_codex = GitHubCodexIntegration()