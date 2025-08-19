"""
Tests for translating processing_filters.yaml into allowed pairs for SQL selection.

Checklist:
- Build pairs for (a) type with subtypes, (b) type with empty subtypes,
  (c) missing subtype field, (d) duplicate subtypes, (e) unknown types.
- Deduplication and stable order.
- Empty result short-circuit.
"""

import pytest


@pytest.mark.skip(reason="TODO: implement filter translation tests")
def test_build_allowed_pairs_variants():
    pass


@pytest.mark.skip(reason="TODO: implement deduplication and stable order tests")
def test_allowed_pairs_dedup_and_order():
    pass


@pytest.mark.skip(reason="TODO: implement empty result short-circuit tests")
def test_empty_allowed_pairs_short_circuit():
    pass


