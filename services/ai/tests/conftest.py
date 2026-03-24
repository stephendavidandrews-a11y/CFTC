"""Root conftest for AI service tests.

Previously contained a pytest_collection_modifyitems hook that forced
test_bundle_review.py to run last, masking a test-isolation bug where
tests/new/conftest.py's per-test TestClient lifespan shutdown poisoned
the module-level _ready flag. That root cause is now fixed directly in
tests/new/conftest.py (restoring _ready after TestClient exit), so the
ordering hack is no longer needed.
"""
