from pathlib import Path
import hcl2
import pytest

ROOT = Path(__file__).resolve().parents[1]
@pytest.mark.parametrize('path', list(ROOT.rglob('*.tf')))
def test_hcl_syntax(path):
    with path.open() as stream:
        assert hcl2.load(stream)
