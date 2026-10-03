import os, tempfile

# Tests must never touch the real data/reviews.json (the expert's confirmations) or call paid providers.
os.environ["APPRENTICE_REVIEWS_FILE"] = os.path.join(tempfile.mkdtemp(), "reviews.json")
os.environ["APPRENTICE_OFFLINE"] = "1"

os.environ["APPRENTICE_LEARNED_FILE"] = os.path.join(tempfile.mkdtemp(), "learned_map.json")
