"""Root conftest — ensures test isolation for module-level DB fixtures.

test_bundle_review.py uses module-level app.dependency_overrides setup.
Other test files that import the app can clobber those overrides.
This conftest adds a forked-process marker for files that need isolation.
"""


def pytest_collection_modifyitems(items):
    """Mark bundle_review tests to run last (after all other files)."""
    bundle_tests = []
    other_tests = []
    for item in items:
        if "test_bundle_review" in item.nodeid:
            bundle_tests.append(item)
        else:
            other_tests.append(item)
    items[:] = other_tests + bundle_tests
