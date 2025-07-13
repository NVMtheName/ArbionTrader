#!/usr/bin/env python3
"""
Command Line Interface for OpenAI Codex GitHub Integration
Provides direct command-line access to GitHub repositories for AI code editing
"""

import sys
import os
import argparse
import json
import logging
from utils.codex_backend_api import CodexBackendAPI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description='OpenAI Codex GitHub Integration CLI')
    parser.add_argument('--github-token', help='GitHub personal access token')
    parser.add_argument('--openai-key', help='OpenAI API key')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List repositories command
    repos_parser = subparsers.add_parser('repos', help='List repositories')
    repos_parser.add_argument('--org', help='Organization to filter by')
    
    # Read file command
    read_parser = subparsers.add_parser('read', help='Read file from repository')
    read_parser.add_argument('owner', help='Repository owner')
    read_parser.add_argument('repo', help='Repository name')
    read_parser.add_argument('path', help='File path')
    
    # Write file command
    write_parser = subparsers.add_parser('write', help='Write file to repository')
    write_parser.add_argument('owner', help='Repository owner')
    write_parser.add_argument('repo', help='Repository name')
    write_parser.add_argument('path', help='File path')
    write_parser.add_argument('--content', help='File content (or use stdin)')
    write_parser.add_argument('--message', help='Commit message')
    
    # Analyze code command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze code with AI')
    analyze_parser.add_argument('--code', help='Code to analyze (or use stdin)')
    analyze_parser.add_argument('--file', help='File to analyze')
    analyze_parser.add_argument('--language', default='python', help='Programming language')
    
    # Improve code command
    improve_parser = subparsers.add_parser('improve', help='Improve code with AI')
    improve_parser.add_argument('--code', help='Code to improve (or use stdin)')
    improve_parser.add_argument('--file', help='File to improve')
    improve_parser.add_argument('--requirements', required=True, help='Improvement requirements')
    improve_parser.add_argument('--language', default='python', help='Programming language')
    
    # Refactor file command
    refactor_parser = subparsers.add_parser('refactor', help='Refactor file with AI')
    refactor_parser.add_argument('owner', help='Repository owner')
    refactor_parser.add_argument('repo', help='Repository name')
    refactor_parser.add_argument('path', help='File path')
    refactor_parser.add_argument('--goals', required=True, help='Refactoring goals')
    
    # Repository summary command
    summary_parser = subparsers.add_parser('summary', help='Get repository summary')
    summary_parser.add_argument('owner', help='Repository owner')
    summary_parser.add_argument('repo', help='Repository name')
    
    # Files command
    files_parser = subparsers.add_parser('files', help='List repository files')
    files_parser.add_argument('owner', help='Repository owner')
    files_parser.add_argument('repo', help='Repository name')
    files_parser.add_argument('--path', default='', help='Path to explore')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize backend API
    codex_api = CodexBackendAPI(args.github_token, args.openai_key)
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == 'repos':
            repos = codex_api.list_repositories(args.org)
            print(json.dumps(repos, indent=2))
        
        elif args.command == 'read':
            result = codex_api.read_file(args.owner, args.repo, args.path)
            if result['success']:
                print(result['content'])
            else:
                print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
                return 1
        
        elif args.command == 'write':
            content = args.content
            if not content:
                # Read from stdin
                content = sys.stdin.read()
            
            result = codex_api.write_file(args.owner, args.repo, args.path, content, args.message)
            if result['success']:
                print(f"File {args.path} {result['operation']}d successfully")
            else:
                print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
                return 1
        
        elif args.command == 'analyze':
            code = args.code
            if args.file:
                with open(args.file, 'r') as f:
                    code = f.read()
            elif not code:
                # Read from stdin
                code = sys.stdin.read()
            
            result = codex_api.analyze_code(code, args.language)
            if result['success']:
                print(json.dumps(result['analysis'], indent=2))
            else:
                print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
                return 1
        
        elif args.command == 'improve':
            code = args.code
            if args.file:
                with open(args.file, 'r') as f:
                    code = f.read()
            elif not code:
                # Read from stdin
                code = sys.stdin.read()
            
            result = codex_api.improve_code(code, args.requirements, args.language)
            if result['success']:
                print(result['improved_code'])
            else:
                print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
                return 1
        
        elif args.command == 'refactor':
            result = codex_api.refactor_file(args.owner, args.repo, args.path, args.goals)
            if result.get('success'):
                print(f"Refactoring completed successfully")
                print(f"Branch: {result.get('branch')}")
                if result.get('pull_request'):
                    print(f"Pull Request: {result['pull_request'].get('html_url')}")
            else:
                print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
                return 1
        
        elif args.command == 'summary':
            result = codex_api.get_repository_summary(args.owner, args.repo)
            if result['success']:
                print(json.dumps(result, indent=2))
            else:
                print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
                return 1
        
        elif args.command == 'files':
            files = codex_api.get_repository_files(args.owner, args.repo, args.path)
            for file in files:
                file_type = file.get('type', 'unknown')
                name = file.get('name', 'unknown')
                print(f"{file_type:10} {name}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())