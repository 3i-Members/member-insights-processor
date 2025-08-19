"""
Tests for the bounded-parallel dispatcher loop.

Checklist:
- Never schedules more than max_concurrent_contacts
- No duplicate scheduling within a run
- Re-query uses (offset=current_inflight, limit=fill+current_inflight)
- Exits when SQL returns 0 rows and in_flight drains
- Continues after a worker failure and aggregates error summary
"""

import pytest


@pytest.mark.skip(reason="TODO: implement dispatcher loop tests with stubbed query runner")
def test_dispatcher_loop_behavior():
    pass


