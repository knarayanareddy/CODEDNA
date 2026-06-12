"""Pytest configuration and fixtures for CodeDNA tests."""
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_python_file(temp_dir):
    file_path = temp_dir / "sample.py"
    file_path.write_text('''
def hello():
    """Say hello."""
    print("Hello, World!")

def add(a, b):
    """Add two numbers."""
    return a + b

class Calculator:
    """Simple calculator."""
    def __init__(self):
        self.result = 0
    def add(self, value):
        self.result += value
        return self.result
''')
    return file_path

@pytest.fixture
def sample_git_repo(temp_dir):
    import subprocess
    repo_dir = temp_dir / "test_repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)
    (repo_dir / "main.py").write_text('''
def main():
    print("Hello")

if __name__ == "__main__":
    main()
''')
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True)
    return repo_dir

@pytest.fixture
def sample_feature_vector():
    from codedna.harvester.features import FeatureVector
    return FeatureVector(snake_case_ratio=0.8, single_char_var_rate=0.2, avg_function_length=15.0)

@pytest.fixture
def harvester_config():
    from codedna.harvester.language_adapter import HarvesterConfig
    return HarvesterConfig(store_bodies=False, max_file_bytes=1048576, language="python")

@pytest.fixture(autouse=True)
def reset_db_state():
    yield
    from codedna.db.session import close_engine
    close_engine()
