"""
Tests for observability/logging of dispatcher and claims.

Checklist:
- Logs include job_start_time, max_concurrent_contacts, allowed_pairs summary size
- Per re-query: in_flight, offset, limit, returned_rows, scheduled
- Claim acquire/skip/release events
"""

import pytest


@pytest.mark.skip(reason="TODO: implement logging assertions with caplog")
def test_observability_logging():
    pass


