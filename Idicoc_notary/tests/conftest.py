import os
import pytest
import shutil

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_results():
    """Fixture to clean up tests/results/ directory before and after running tests."""
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    if os.path.exists(results_dir):
        shutil.rmtree(results_dir)
    os.makedirs(results_dir, exist_ok=True)
    
    # Also remove root level ctm_root.txt or ctm_nodes.json if they leaked
    for filename in ["ctm_root.txt", "ctm_nodes.json"]:
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except OSError:
                pass

    yield

    if os.path.exists(results_dir):
        shutil.rmtree(results_dir)
