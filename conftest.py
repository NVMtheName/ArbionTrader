import os
import pytest

@pytest.fixture
def api_key():
    """Provide OpenAI API key for tests"""
    return os.environ.get("OPENAI_API_KEY", "test")
