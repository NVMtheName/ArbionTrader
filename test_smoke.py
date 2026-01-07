"""
Smoke tests for CI/CD pipeline
These tests are lightweight and don't require full app initialization
"""

import pytest
import sys
import os

# Mark all tests in this file as smoke tests
pytestmark = pytest.mark.smoke


class TestEnvironment:
    """Test that the environment is set up correctly"""

    def test_python_version(self):
        """Verify Python version is 3.11+"""
        assert sys.version_info >= (3, 11), f"Python 3.11+ required, got {sys.version_info}"

    def test_required_directories_exist(self):
        """Verify required directories exist"""
        required_dirs = ['utils', 'routes', 'templates', 'static']
        for dir_name in required_dirs:
            assert os.path.isdir(dir_name), f"Required directory '{dir_name}' not found"

    def test_required_files_exist(self):
        """Verify required files exist"""
        required_files = [
            'app.py',
            'models.py',
            'main.py',
            'worker.py',
            'Procfile',
            'pyproject.toml'
        ]
        for file_name in required_files:
            assert os.path.isfile(file_name), f"Required file '{file_name}' not found"


class TestUtilities:
    """Test utility modules can be imported"""

    def test_import_pkce_utils(self):
        """Test that PKCE utilities can be imported"""
        try:
            from utils.pkce_utils import generate_pkce_pair, validate_pkce_pair
            assert callable(generate_pkce_pair)
            assert callable(validate_pkce_pair)
        except ImportError as e:
            pytest.fail(f"Failed to import PKCE utils: {e}")

    def test_pkce_generation(self):
        """Test PKCE code verifier and challenge generation"""
        from utils.pkce_utils import generate_pkce_pair

        verifier, challenge = generate_pkce_pair()

        # Verify lengths (RFC 7636 requirements)
        assert len(verifier) >= 43, "Code verifier must be at least 43 characters"
        assert len(challenge) == 43, "SHA256 code challenge should be 43 characters"

        # Verify they're different
        assert verifier != challenge, "Code verifier and challenge must be different"

        # Verify challenge is base64url encoded
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', challenge), "Code challenge must be base64url encoded"

    def test_pkce_validation(self):
        """Test PKCE validation logic"""
        from utils.pkce_utils import generate_pkce_pair, validate_pkce_pair

        verifier, challenge = generate_pkce_pair()

        # Valid pair should validate
        assert validate_pkce_pair(verifier, challenge) is True

        # Different verifier should not validate
        verifier2, challenge2 = generate_pkce_pair()
        assert validate_pkce_pair(verifier2, challenge) is False

    def test_import_exceptions(self):
        """Test that custom exceptions can be imported"""
        try:
            from utils.exceptions import (
                ArbionBaseException,
                OrderExecutionError,
                RiskLimitExceededError
            )
            assert issubclass(OrderExecutionError, ArbionBaseException)
            assert issubclass(RiskLimitExceededError, ArbionBaseException)
        except ImportError as e:
            pytest.fail(f"Failed to import custom exceptions: {e}")


class TestConfiguration:
    """Test configuration and environment variables"""

    def test_environment_variables_accessible(self):
        """Test that environment variables can be accessed"""
        # Just verify os.environ works, don't check for specific values
        assert isinstance(os.environ, dict)
        assert len(os.environ) > 0

    def test_encryption_utilities_importable(self):
        """Test that encryption utilities can be imported"""
        try:
            from utils.encryption import get_encryption_key
            assert callable(get_encryption_key)
        except ImportError as e:
            pytest.fail(f"Failed to import encryption utilities: {e}")


class TestModels:
    """Test that model definitions are valid"""

    def test_models_file_syntax(self):
        """Test that models.py has valid syntax"""
        try:
            import ast
            with open('models.py', 'r') as f:
                code = f.read()
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in models.py: {e}")

    def test_app_file_syntax(self):
        """Test that app.py has valid syntax"""
        try:
            import ast
            with open('app.py', 'r') as f:
                code = f.read()
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in app.py: {e}")


class TestDocumentation:
    """Test that documentation exists"""

    def test_phase_reports_exist(self):
        """Verify Phase completion reports exist"""
        reports = [
            'PRODUCTION_READINESS_REPORT.md',
            'PHASE_2_COMPLETE.md',
            'PHASE_3_COMPLETE.md'
        ]
        for report in reports:
            assert os.path.isfile(report), f"Missing report: {report}"

    def test_test_documentation_exists(self):
        """Verify test documentation exists"""
        assert os.path.isfile('TEST_SUITE_README.md'), "Missing TEST_SUITE_README.md"
        assert os.path.isfile('PKCE_INTEGRATION_COMPLETE.md'), "Missing PKCE_INTEGRATION_COMPLETE.md"


if __name__ == '__main__':
    # Run smoke tests when executed directly
    pytest.main([__file__, '-v', '-m', 'smoke'])
