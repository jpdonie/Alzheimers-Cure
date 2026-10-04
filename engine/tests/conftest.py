import os, tempfile

# Tests must never touch the real data/reviews.json (the expert's confirmations) or call paid providers.
os.environ["APPRENTICE_REVIEWS_FILE"] = os.path.join(tempfile.mkdtemp(), "reviews.json")
os.environ["APPRENTICE_OFFLINE"] = "1"

os.environ["APPRENTICE_LEARNED_FILE"] = os.path.join(tempfile.mkdtemp(), "learned_map.json")


import pytest


@pytest.fixture(autouse=True)
def _clean_review_state():
    """Every test starts with no expert reviews, so a failing test can never leak a 'rejected' rule into the next one."""
    from engine.session import reviews_path
    reviews_path().unlink(missing_ok=True)
    yield
    reviews_path().unlink(missing_ok=True)
