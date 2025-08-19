"""
Tests for LocalFileClaimer duplicate-safety.

Checklist:
- Atomic create: concurrent acquire → exactly one success
- TTL expiry: re-acquire after expiry succeeds
- Release removes lock; acquire succeeds
- Stale file handling
"""

import pytest


@pytest.mark.skip(reason="TODO: implement LocalFileClaimer tests")
def test_local_file_claimer_behavior():
    pass


