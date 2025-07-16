# OpenAI Codex Integration Guide for Arbion AI Trading Platform

## Overview

This guide provides comprehensive instructions for integrating OpenAI Codex with the Arbion AI Trading Platform's GitHub repository management system.

## Backend API Access

### 1. Direct Function Interfaces

The simplest way to integrate with Codex is through direct function calls:

```python
from utils.codex_backend_api import (
    codex_list_repos,
    codex_read_file,
    codex_write_file,
    codex_analyze_code,
    codex_improve_code,
    codex_refactor_file,
    codex_repo_summary
)

# List repositories
repos = codex_list_repos()

# Read a file
file_data = codex_read_file('owner', 'repo', 'path/to/file.py')

# Write a file
result = codex_write_file('owner', 'repo', 'path/to/file.py', 'content', 'commit message')

# Analyze code
analysis = codex_analyze_code('python code here', 'python')

# Improve code
improved = codex_improve_code('code', 'make it more efficient', 'python')

# Refactor file
refactor_result = codex_refactor_file('owner', 'repo', 'file.py', 'add error handling')

# Get repository summary
summary = codex_repo_summary('owner', 'repo')
```

### 2. Backend API Class

For more advanced usage, use the `CodexBackendAPI` class directly:

```python
from utils.codex_backend_api import CodexBackendAPI

# Initialize with credentials
api = CodexBackendAPI(github_token='your_token', openai_api_key='your_key')

# Or use environment variables
api = CodexBackendAPI()  # Uses GITHUB_TOKEN and OPENAI_API_KEY

# Bulk operations
operations = [
    {'type': 'read', 'file_path': 'src/main.py'},
    {'type': 'analyze', 'file_path': 'src/utils.py', 'language': 'python'},
    {'type': 'improve', 'file_path': 'src/api.py', 'requirements': 'add error handling'}
]

results = api.bulk_file_operations('owner', 'repo', operations)
```

## Command Line Interface

### Installation

The CLI is already executable and ready to use:

```bash
./codex_cli.py --help
```

### Usage Examples

```bash
# List repositories
./codex_cli.py repos

# Read a file
./codex_cli.py read owner repo path/to/file.py

# Write a file
echo "print('Hello World')" | ./codex_cli.py write owner repo hello.py --message "Add hello world"

# Analyze code
./codex_cli.py analyze --code "def hello(): print('hi')" --language python

# Improve code
./codex_cli.py improve --code "def add(a,b): return a+b" --requirements "add error handling"

# Refactor file
./codex_cli.py refactor owner repo main.py --goals "improve performance"

# Get repository summary
./codex_cli.py summary owner repo

# List files
./codex_cli.py files owner repo --path src/
```

## REST API Endpoints

The system provides HTTP endpoints for external integration:

### Base URL
```
http://localhost:5001/api/codex/
```

### Endpoints

#### GET /repositories
List all accessible repositories
```bash
curl "http://localhost:5001/api/codex/repositories"
```

#### GET /repository/{owner}/{repo}/files
Get repository file structure
```bash
curl "http://localhost:5001/api/codex/repository/owner/repo/files?path=src/"
```

#### GET /repository/{owner}/{repo}/file
Read a file
```bash
curl "http://localhost:5001/api/codex/repository/owner/repo/file?path=main.py"
```

#### POST /repository/{owner}/{repo}/file
Write/update a file
```bash
curl -X POST "http://localhost:5001/api/codex/repository/owner/repo/file" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "main.py",
    "content": "print(\"Hello World\")",
    "commit_message": "Update main.py"
  }'
```

#### POST /analyze
Analyze code
```bash
curl -X POST "http://localhost:5001/api/codex/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def hello(): print(\"hi\")",
    "language": "python"
  }'
```

#### POST /improve
Improve code
```bash
curl -X POST "http://localhost:5001/api/codex/improve" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def add(a,b): return a+b",
    "requirements": "add error handling",
    "language": "python"
  }'
```

#### POST /repository/{owner}/{repo}/refactor
Refactor a file
```bash
curl -X POST "http://localhost:5001/api/codex/repository/owner/repo/refactor" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "main.py",
    "refactoring_goals": "improve performance"
  }'
```

#### GET /repository/{owner}/{repo}/summary
Get repository summary
```bash
curl "http://localhost:5001/api/codex/repository/owner/repo/summary"
```

#### POST /bulk-operations
Perform bulk operations
```bash
curl -X POST "http://localhost:5001/api/codex/bulk-operations" \
  -H "Content-Type: application/json" \
  -d '{
    "owner": "owner",
    "repo": "repo",
    "operations": [
      {"type": "read", "file_path": "main.py"},
      {"type": "analyze", "file_path": "utils.py", "language": "python"}
    ]
  }'
```

## Configuration

### Environment Variables

Set these environment variables for authentication:

```bash
export GITHUB_TOKEN="your_github_personal_access_token"
export OPENAI_API_KEY="your_openai_api_key"
```

### GitHub Token Requirements

The GitHub token needs the following permissions:
- `repo` - Full repository access
- `workflow` - GitHub Actions workflow access (optional)
- `read:org` - Organization reading access (optional)

### OpenAI API Key

Ensure you have access to OpenAI's API with sufficient credits for code analysis and improvement operations.

## Error Handling

All functions return structured responses with success/error indicators:

```python
{
    "success": True,
    "data": {...},
    "error": None
}
```

Or in case of errors:

```python
{
    "success": False,
    "data": None,
    "error": "Error message"
}
```

## Integration Examples

### Example 1: Repository Analysis

```python
from utils.codex_backend_api import CodexBackendAPI

api = CodexBackendAPI()

# Get repository summary
summary = api.get_repository_summary('owner', 'repo')

# Analyze key Python files
for file in summary['key_files']:
    if file['name'].endswith('.py'):
        analysis = api.analyze_code(file['content_preview'], 'python')
        print(f"Analysis for {file['path']}: {analysis}")
```

### Example 2: Code Improvement Pipeline

```python
from utils.codex_backend_api import CodexBackendAPI

api = CodexBackendAPI()

# Read source file
file_data = api.read_file('owner', 'repo', 'src/main.py')

if file_data['success']:
    # Analyze the code
    analysis = api.analyze_code(file_data['content'], 'python')
    
    # Improve the code
    improved = api.improve_code(
        file_data['content'],
        'add error handling and improve performance',
        'python'
    )
    
    if improved['success']:
        # Write improved code back
        result = api.write_file(
            'owner', 'repo', 'src/main.py',
            improved['improved_code'],
            'Improved code with error handling and performance optimizations'
        )
```

## Deployment Configuration

The system is configured for Codex deployment with:

- **codex.json**: Main configuration file
- **.python-version**: Python version specification
- **.codexsetup**: Codex-specific setup configuration
- **Procfile**: Process configuration
- **scripts/setup.sh**: Setup script
- **scripts/start.sh**: Start script

## Health Check

Test the system health:

```bash
curl "http://localhost:5001/api/codex/status"
```

This will return system status and configuration information.

## Support

For issues or questions about the Codex integration, refer to the project documentation or contact the development team.