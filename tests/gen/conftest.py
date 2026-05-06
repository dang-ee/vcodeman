from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def simple_dir() -> Path:
    return FIXTURES_DIR / "simple"
