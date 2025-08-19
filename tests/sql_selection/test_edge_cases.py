"""
Edge case tests for SQL selection.

Checklist:
- Empty allowed_pairs → short-circuit / WHERE FALSE
- All eligible ENIs are banned type → zero
- Very large seen set still works (OFFSET-driven)
- NULL subtype mapping to '__NULL__'
"""

import pytest


@pytest.mark.skip(reason="TODO: implement SQL selection edge case tests")
def test_edge_cases_selection():
    pass


