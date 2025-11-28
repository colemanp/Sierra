#!/usr/bin/env python
"""Test MCP weight tools with token assertions

Run: python scripts/test_mcp.py
"""
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from health_import.mcp.weight import (
    get_weight_summary,
    get_weight_trend,
    get_weight_records,
    get_weight_stats,
    get_weight_compare,
)
from health_import.mcp.nutrition import (
    get_nutrition_summary,
    get_nutrition_trend,
    get_nutrition_day,
    get_nutrition_stats,
    get_nutrition_compare,
)
from health_import.mcp.activity import (
    get_activity_summary,
    get_activity_trend,
    get_activity_records,
    get_activity_stats,
    get_activity_compare,
)


def estimate_tokens(data: dict) -> int:
    """Estimate token count from JSON length (len/4 approximation)"""
    return len(json.dumps(data, default=str)) // 4


def test_weight_summary():
    """Test weight_summary - should be ~40 tokens"""
    result = get_weight_summary()
    tokens = estimate_tokens(result)
    print(f"\n=== weight_summary ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "cur" in result, "Missing 'cur' field"
    assert "rng" in result, "Missing 'rng' field"
    assert tokens < 80, f"Token count too high: {tokens} > 80"
    print("[PASS]")
    return tokens


def test_weight_trend():
    """Test weight_trend - should scale with limit"""
    # Test with 3 months
    result = get_weight_trend("month", 3)
    tokens = estimate_tokens(result)
    print(f"\n=== weight_trend (3 months) ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "d" in result, "Missing 'd' field"
    assert len(result["d"]) <= 3, f"Too many periods: {len(result['d'])}"
    assert "m" in result["d"][0], "Missing 'm' (muscle) in trend data"
    assert tokens < 100, f"Token count too high for 3 months: {tokens} > 100"
    print("[PASS]")

    # Test with 12 months
    result = get_weight_trend("month", 12)
    tokens = estimate_tokens(result)
    print(f"\n=== weight_trend (12 months) ===")
    print(f"Tokens: {tokens}")

    assert tokens < 300, f"Token count too high for 12 months: {tokens} > 300"
    print("[PASS]")
    return tokens


def test_weight_records():
    """Test weight_records - should paginate properly"""
    # Test with 5 records
    result = get_weight_records(page=1, page_size=5)
    tokens = estimate_tokens(result)
    print(f"\n=== weight_records (5 records) ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "r" in result, "Missing 'r' field"
    assert "pg" in result, "Missing 'pg' field"
    assert "pgs" in result, "Missing 'pgs' field"
    assert "n" in result, "Missing 'n' field"
    assert len(result["r"]) <= 5, f"Too many records: {len(result['r'])}"
    assert tokens < 150, f"Token count too high for 5 records: {tokens} > 150"
    print("[PASS]")

    # Test max page size
    result = get_weight_records(page=1, page_size=50)
    tokens = estimate_tokens(result)
    print(f"\n=== weight_records (50 records) ===")
    print(f"Tokens: {tokens}")

    assert len(result["r"]) <= 50, f"Too many records: {len(result['r'])}"
    assert tokens < 1500, f"Token count too high for 50 records: {tokens} > 1500"
    print("[PASS]")
    return tokens


def test_weight_stats():
    """Test weight_stats - should be ~50 tokens"""
    result = get_weight_stats()
    tokens = estimate_tokens(result)
    print(f"\n=== weight_stats ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "wt" in result, "Missing 'wt' field"
    assert "chg" in result, "Missing 'chg' field"
    assert tokens < 100, f"Token count too high: {tokens} > 100"
    print("[PASS]")
    return tokens


def test_weight_compare():
    """Test weight_compare - should be ~60 tokens"""
    result = get_weight_compare(
        "2024-01-01", "2024-03-31",
        "2024-04-01", "2024-06-30"
    )
    tokens = estimate_tokens(result)
    print(f"\n=== weight_compare ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "p1" in result, "Missing 'p1' field"
    assert "p2" in result, "Missing 'p2' field"
    assert "d" in result, "Missing 'd' field"
    assert tokens < 100, f"Token count too high: {tokens} > 100"
    print("[PASS]")
    return tokens


# ============================================================================
# Nutrition Tests
# ============================================================================


def test_nutrition_summary():
    """Test nutrition_summary - should be ~40 tokens"""
    result = get_nutrition_summary()
    tokens = estimate_tokens(result)
    print(f"\n=== nutrition_summary ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "cur" in result, "Missing 'cur' field"
    assert "rng" in result, "Missing 'rng' field"
    assert "cal" in result["cur"], "Missing 'cal' in cur"
    assert tokens < 60, f"Token count too high: {tokens} > 60"
    print("[PASS]")
    return tokens


def test_nutrition_trend():
    """Test nutrition_trend - should scale with limit"""
    result = get_nutrition_trend("day", 3)
    tokens = estimate_tokens(result)
    print(f"\n=== nutrition_trend (3 days) ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "d" in result, "Missing 'd' field"
    assert len(result["d"]) <= 3, f"Too many periods: {len(result['d'])}"
    assert "p" in result["d"][0], "Missing 'p' (period) in trend data"
    assert "cal" in result["d"][0], "Missing 'cal' in trend data"
    assert tokens < 100, f"Token count too high: {tokens} > 100"
    print("[PASS]")
    return tokens


def test_nutrition_day():
    """Test nutrition_day - item-level detail"""
    result = get_nutrition_day("2025-11-27")
    tokens = estimate_tokens(result)
    print(f"\n=== nutrition_day ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "d" in result, "Missing 'd' field"
    assert "tot" in result, "Missing 'tot' field"
    assert "items" in result, "Missing 'items' field"
    assert len(result["items"]) > 0, "No items returned"
    assert "food" in result["items"][0], "Missing 'food' in items"
    print("[PASS]")
    return tokens


def test_nutrition_stats():
    """Test nutrition_stats - should be ~60 tokens"""
    result = get_nutrition_stats()
    tokens = estimate_tokens(result)
    print(f"\n=== nutrition_stats ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "cal" in result, "Missing 'cal' field"
    assert "avg" in result["cal"], "Missing 'avg' in cal"
    assert tokens < 100, f"Token count too high: {tokens} > 100"
    print("[PASS]")
    return tokens


def test_nutrition_compare():
    """Test nutrition_compare - should be ~70 tokens"""
    result = get_nutrition_compare(
        "2025-11-20", "2025-11-23",
        "2025-11-24", "2025-11-27"
    )
    tokens = estimate_tokens(result)
    print(f"\n=== nutrition_compare ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "p1" in result, "Missing 'p1' field"
    assert "p2" in result, "Missing 'p2' field"
    assert "d" in result, "Missing 'd' field"
    assert tokens < 120, f"Token count too high: {tokens} > 120"
    print("[PASS]")
    return tokens


# ============================================================================
# Activity Tests
# ============================================================================


def test_activity_summary():
    """Test activity_summary - should be ~50 tokens"""
    result = get_activity_summary()
    tokens = estimate_tokens(result)
    print(f"\n=== activity_summary ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "last" in result, "Missing 'last' field"
    assert "rng" in result, "Missing 'rng' field"
    assert "type" in result["last"], "Missing 'type' in last"
    assert tokens < 80, f"Token count too high: {tokens} > 80"
    print("[PASS]")
    return tokens


def test_activity_trend():
    """Test activity_trend - should scale with limit"""
    result = get_activity_trend("week", 4)
    tokens = estimate_tokens(result)
    print(f"\n=== activity_trend (4 weeks) ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "d" in result, "Missing 'd' field"
    assert len(result["d"]) <= 4, f"Too many periods: {len(result['d'])}"
    assert "p" in result["d"][0], "Missing 'p' (period) in trend data"
    assert "n" in result["d"][0], "Missing 'n' (count) in trend data"
    assert tokens < 150, f"Token count too high: {tokens} > 150"
    print("[PASS]")
    return tokens


def test_activity_records():
    """Test activity_records - should paginate properly"""
    result = get_activity_records(page=1, page_size=5)
    tokens = estimate_tokens(result)
    print(f"\n=== activity_records (5 records) ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "r" in result, "Missing 'r' field"
    assert "pg" in result, "Missing 'pg' field"
    assert "pgs" in result, "Missing 'pgs' field"
    assert "n" in result, "Missing 'n' field"
    assert len(result["r"]) <= 5, f"Too many records: {len(result['r'])}"
    assert "type" in result["r"][0], "Missing 'type' in records"
    assert tokens < 250, f"Token count too high: {tokens} > 250"
    print("[PASS]")

    # Test with activity_type filter
    result = get_activity_records(activity_type="running", page=1, page_size=5)
    tokens = estimate_tokens(result)
    print(f"\n=== activity_records (running only) ===")
    print(f"Tokens: {tokens}")

    for rec in result["r"]:
        assert rec["type"] == "running", f"Expected 'running', got '{rec['type']}'"
    print("[PASS]")
    return tokens


def test_activity_stats():
    """Test activity_stats - should be ~60 tokens"""
    result = get_activity_stats()
    tokens = estimate_tokens(result)
    print(f"\n=== activity_stats ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "n" in result, "Missing 'n' field"
    assert "dur" in result, "Missing 'dur' field"
    assert "tot" in result["dur"], "Missing 'tot' in dur"
    assert tokens < 120, f"Token count too high: {tokens} > 120"
    print("[PASS]")
    return tokens


def test_activity_compare():
    """Test activity_compare - should be ~70 tokens"""
    result = get_activity_compare(
        "2025-10-01", "2025-10-31",
        "2025-11-01", "2025-11-24"
    )
    tokens = estimate_tokens(result)
    print(f"\n=== activity_compare ===")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"Tokens: {tokens}")

    assert "p1" in result, "Missing 'p1' field"
    assert "p2" in result, "Missing 'p2' field"
    assert "d" in result, "Missing 'd' field"
    assert tokens < 120, f"Token count too high: {tokens} > 120"
    print("[PASS]")
    return tokens


def main():
    """Run all tests"""
    print("=" * 60)
    print("MCP Tools Token Tests")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    # Weight tests
    weight_tests = [
        test_weight_summary,
        test_weight_trend,
        test_weight_records,
        test_weight_stats,
        test_weight_compare,
    ]

    # Nutrition tests
    nutrition_tests = [
        test_nutrition_summary,
        test_nutrition_trend,
        test_nutrition_day,
        test_nutrition_stats,
        test_nutrition_compare,
    ]

    # Activity tests
    activity_tests = [
        test_activity_summary,
        test_activity_trend,
        test_activity_records,
        test_activity_stats,
        test_activity_compare,
    ]

    for test_fn in weight_tests + nutrition_tests + activity_tests:
        try:
            test_fn()
            tests_passed += 1
        except AssertionError as e:
            print(f"[FAIL]: {e}")
            tests_failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)

    return 0 if tests_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
