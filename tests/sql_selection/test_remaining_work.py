"""
Tests for remaining work semantics in selection SQL.

Checklist scenarios:
- Never processed
- Partially processed
- Fully processed
- Processed under different prompt/generator
- Processed after job_start_time (excluded)
- Processed before job_start_time with remaining ENIs
"""

import pytest


@pytest.mark.skip(reason="TODO: implement remaining work semantics tests")
def test_remaining_work_scenarios():
    pass


