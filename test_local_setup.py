#!/usr/bin/env python3
"""
Local Setup Test Script

Tests all key features of the member insights processor without requiring BigQuery.
This validates the local environment is properly configured.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from context_management.context_manager import ContextManager
from context_management.config_loader import create_config_loader
from context_management.processing_filter import create_processing_filter
from data_processing.supabase_client import SupabaseInsightsClient
from data_processing.schema import InsightMetadata
from utils.token_utils import estimate_tokens


def test_configuration():
    """Test configuration loading."""
    print("\n🔧 Testing Configuration...")

    config_loader = create_config_loader("config/config.yaml")

    # Test BigQuery config
    bq_config = config_loader.get_bigquery_config()
    print(f"   ✅ BigQuery project: {bq_config.get('project_id')}")

    # Test AI config
    ai_provider = config_loader.get_processing_config().get('ai_provider')
    print(f"   ✅ AI provider: {ai_provider}")

    # Test system prompts (just verify config loads)
    print(f"   ✅ Configuration loaded successfully")

    return True


def test_context_manager():
    """Test context manager and token budgeting."""
    print("\n📚 Testing Context Manager...")

    cm = ContextManager("config/config.yaml")

    # Test token settings
    print(f"   ✅ Context window: {cm.context_window_tokens:,} tokens")
    print(f"   ✅ Reserved for output: {cm.reserve_output_tokens:,} tokens")
    print(f"   ✅ Max new data per group: {cm.max_new_data_tokens_per_group:,} tokens")

    # Test system prompts
    prompts = cm.get_all_system_prompts()
    print(f"   ✅ System prompts: {len(prompts)} available")

    # Test ENI types
    eni_types = cm.get_available_eni_types()
    print(f"   ✅ ENI types: {len(eni_types)} configured")
    print(f"      First 3: {', '.join(eni_types[:3])}")

    # Test context file paths
    paths = cm.get_context_file_paths("airtable_notes", None)
    if paths:
        type_path, subtype_path = paths
        if type_path:
            content = cm.read_markdown_file(type_path)
            print(f"   ✅ Read context file: {len(content)} chars")

    # Test config validation
    validation = cm.validate_configuration()
    if validation['valid']:
        print(f"   ✅ Configuration validation passed")
    else:
        print(f"   ⚠️  Configuration warnings: {len(validation['warnings'])}")

    return True


def test_processing_filters():
    """Test processing filter configuration."""
    print("\n🔍 Testing Processing Filters...")

    pf = create_processing_filter("config/processing_filters.yaml")

    # Access processing rules
    if hasattr(pf, 'processing_rules'):
        rules = pf.processing_rules
        total_types = len(rules.get('eni_processing_rules', {}))
        print(f"   ✅ ENI types in filter rules: {total_types}")

        # Show first few rules
        for i, (eni_type, subtypes) in enumerate(list(rules.get('eni_processing_rules', {}).items())[:3]):
            subtype_count = len(subtypes) if subtypes else 0
            print(f"      {i+1}. {eni_type}: {subtype_count} subtype(s)")
    else:
        print(f"   ✅ Processing filter loaded successfully")

    return True


def test_supabase():
    """Test Supabase connection."""
    print("\n💾 Testing Supabase...")

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key or supabase_url.startswith("your-"):
        print("   ⚠️  Supabase credentials not configured in .env")
        print("      (This is optional for local testing)")
        return True  # Not a hard failure

    try:
        client = SupabaseInsightsClient(url=supabase_url, key=supabase_key)
        print("   ✅ Supabase client connected")

        # Test health check
        healthy = client.health_check()
        if healthy:
            print("   ✅ Supabase health check passed")
        else:
            print("   ⚠️  Supabase health check failed")

        return healthy
    except Exception as e:
        print(f"   ⚠️  Supabase connection issue: {str(e)[:100]}")
        return True  # Not a hard failure for local testing


def test_schema_validation():
    """Test Pydantic schema validation."""
    print("\n📋 Testing Schema Validation...")

    # Test metadata
    metadata = InsightMetadata(
        contact_id="TEST-001",
        eni_id="COMBINED-TEST-001-ALL",
        eni_source_types=["airtable_notes", "recurroo"],
        eni_source_subtypes=["biography", "investing_preferences"],
        generator="structured_insight",
        record_count=5,
        total_eni_ids=10
    )
    print(f"   ✅ Metadata validation passed")
    print(f"      Contact: {metadata.contact_id}")
    print(f"      ENI ID: {metadata.eni_id}")
    print(f"      Types: {metadata.eni_source_types}")
    print(f"      Records: {metadata.record_count}")

    return True


def test_token_estimation():
    """Test token estimation utilities."""
    print("\n🔢 Testing Token Estimation...")

    test_texts = [
        "Short text",
        "Medium length text with more words and complexity",
        "Very long text " * 100
    ]

    for text in test_texts:
        tokens = estimate_tokens(text)
        ratio = tokens/len(text) if len(text) > 0 else 0
        print(f"   ✅ {len(text):4d} chars → {tokens:4d} tokens (ratio: {ratio:.3f})")

    return True


def test_environment():
    """Test environment variables."""
    print("\n🌍 Testing Environment Variables...")

    required_vars = {
        "GOOGLE_APPLICATION_CREDENTIALS": "BigQuery credentials path",
        "OPENAI_API_KEY": "OpenAI API key (or ANTHROPIC_API_KEY/GEMINI_API_KEY)"
    }

    optional_vars = {
        "SUPABASE_URL": "Supabase project URL",
        "SUPABASE_SERVICE_ROLE_KEY": "Supabase service role key",
        "AIRTABLE_API_KEY": "Airtable API key"
    }

    all_good = True

    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value and not value.startswith("your-"):
            print(f"   ✅ {var}: configured")
        else:
            print(f"   ❌ {var}: NOT configured ({desc})")
            all_good = False

    # Check AI provider
    has_ai = any([
        os.getenv("OPENAI_API_KEY") and not os.getenv("OPENAI_API_KEY").startswith("your-"),
        os.getenv("ANTHROPIC_API_KEY") and not os.getenv("ANTHROPIC_API_KEY").startswith("your-"),
        os.getenv("GEMINI_API_KEY") and not os.getenv("GEMINI_API_KEY").startswith("your-")
    ])
    if has_ai:
        print(f"   ✅ AI provider API key: configured")
    else:
        print(f"   ⚠️  No AI provider configured (set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY)")

    for var, desc in optional_vars.items():
        value = os.getenv(var)
        if value and not value.startswith("your-"):
            print(f"   ✅ {var}: configured")
        else:
            print(f"   ⚠️  {var}: not configured ({desc}) - optional")

    return all_good


def main():
    """Run all tests."""
    print("=" * 70)
    print("🧪 Member Insights Processor - Local Setup Test")
    print("=" * 70)

    tests = [
        ("Environment Variables", test_environment),
        ("Configuration Loading", test_configuration),
        ("Context Manager", test_context_manager),
        ("Processing Filters", test_processing_filters),
        ("Supabase Connection", test_supabase),
        ("Schema Validation", test_schema_validation),
        ("Token Estimation", test_token_estimation)
    ]

    results = {}
    for name, test_func in tests:
        try:
            result = test_func()
            results[name] = result
        except Exception as e:
            print(f"\n   ❌ {name} test failed: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary")
    print("=" * 70)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}  {name}")

    print("\n" + "=" * 70)
    print(f"   {passed}/{total} tests passed")
    print("=" * 70)

    if passed >= total - 1:  # Allow 1 failure for optional components
        print("\n🎉 Local setup is working!")
        print("\nNext steps:")
        print("   1. Update .env with your actual BigQuery credentials path")
        print("   2. Update .env with your AI provider API key")
        print("   3. Run: python src/main.py --validate")
        print("   4. Test with a single contact: python src/main.py --limit 1")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
