#!/usr/bin/env python3
"""
API Connections Test Suite

This script tests all external API connections including:
- BigQuery connectivity
- Gemini 2.5 Flash API
- Airtable API
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any
import logging

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from data_processing.bigquery_connector import create_bigquery_connector
from context_management.config_loader import create_config_loader
from ai_processing.gemini_processor import create_gemini_processor

# Removed: enhanced_airtable_writer - now consolidated into airtable_writer import create_enhanced_airtable_writer
from output_management.airtable_writer import create_structured_airtable_writer

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class APIConnectionTester:
    """Comprehensive API connection tester."""

    def __init__(self):
        """Initialize the tester with configuration."""
        self.config_loader = create_config_loader("config/config.yaml")
        self.test_results = {}

    def test_environment_variables(self) -> Dict[str, Any]:
        """Test that required environment variables are set."""
        print("🔍 Testing Environment Variables...")

        required_vars = ["PROJECT_ID", "BQ_DATASET", "GOOGLE_CLOUD_PROJECT_ID", "GEMINI_API_KEY"]

        optional_vars = ["AIRTABLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS"]

        results = {
            "status": "success",
            "required_missing": [],
            "optional_missing": [],
            "found_vars": {},
        }

        # Check required variables
        for var in required_vars:
            value = os.getenv(var)
            if value:
                results["found_vars"][var] = f"✅ Set ({len(value)} characters)"
                print(f"   ✅ {var}: Set")
            else:
                results["required_missing"].append(var)
                results["found_vars"][var] = "❌ Not set"
                print(f"   ❌ {var}: Not set")

        # Check optional variables
        for var in optional_vars:
            value = os.getenv(var)
            if value:
                results["found_vars"][var] = f"✅ Set ({len(value)} characters)"
                print(f"   ✅ {var}: Set (optional)")
            else:
                results["optional_missing"].append(var)
                results["found_vars"][var] = "⚠️  Not set (optional)"
                print(f"   ⚠️  {var}: Not set (optional)")

        # Determine overall status
        if results["required_missing"]:
            results["status"] = "failed"
            print(f"   💥 Missing required variables: {', '.join(results['required_missing'])}")
        else:
            print("   🎉 All required environment variables are set!")

        return results

    def test_configuration_loading(self) -> Dict[str, Any]:
        """Test configuration file loading."""
        print("\n📋 Testing Configuration Loading...")

        results = {
            "status": "success",
            "config_loaded": False,
            "sections": {},
            "gemini_config": {},
            "model_name": None,
        }

        try:
            # Test basic config loading
            if self.config_loader.config_data:
                results["config_loaded"] = True
                print("   ✅ Configuration file loaded successfully")
            else:
                results["status"] = "failed"
                print("   ❌ Failed to load configuration file")
                return results

            # Test specific sections
            sections_to_test = ["bigquery", "gemini", "airtable", "processing"]
            for section in sections_to_test:
                try:
                    if section == "bigquery":
                        config = self.config_loader.get_bigquery_config()
                    elif section == "gemini":
                        config = self.config_loader.get_gemini_config()
                    elif section == "airtable":
                        config = self.config_loader.get_airtable_config()
                    elif section == "processing":
                        config = self.config_loader.get_processing_config()

                    if config:
                        results["sections"][section] = "✅ Loaded"
                        print(f"   ✅ {section.title()} configuration loaded")

                        if section == "gemini":
                            results["gemini_config"] = config
                            model_name = config.get("model_name", "Not specified")
                            results["model_name"] = model_name
                            print(f"   📡 Gemini model configured: {model_name}")

                            # Check generation config
                            gen_config = config.get("generation_config", {})
                            if gen_config:
                                print(f"   ⚙️  Generation config: {gen_config}")
                    else:
                        results["sections"][section] = "⚠️  Empty"
                        print(f"   ⚠️  {section.title()} configuration is empty")

                except Exception as e:
                    results["sections"][section] = f"❌ Error: {str(e)}"
                    print(f"   ❌ Error loading {section} config: {str(e)}")

        except Exception as e:
            results["status"] = "failed"
            results["error"] = str(e)
            print(f"   💥 Configuration loading failed: {str(e)}")

        return results

    def test_bigquery_connection(self) -> Dict[str, Any]:
        """Test BigQuery connection."""
        print("\n🗃️  Testing BigQuery Connection...")

        results = {
            "status": "success",
            "connected": False,
            "config_valid": False,
            "test_query": False,
        }

        try:
            # Create BigQuery connector
            bigquery_config = self.config_loader.get_bigquery_config()
            if not bigquery_config:
                results["status"] = "failed"
                results["error"] = "No BigQuery configuration found"
                print("   ❌ No BigQuery configuration found")
                return results

            results["config_valid"] = True
            print(f"   ✅ BigQuery config loaded: {bigquery_config}")

            # Test connection - pass the full config data, not just bigquery section
            bigquery_connector = create_bigquery_connector(self.config_loader.config_data)
            if bigquery_connector.connect():
                results["connected"] = True
                print("   ✅ BigQuery connection successful")

                # Test a simple query
                try:
                    # Try to get basic table info (CNT-TEST likely doesn't exist, so this should return empty)
                    contact_data = bigquery_connector.load_contact_data("CNT-TEST")
                    if contact_data is not None:
                        results["test_query"] = True
                        print(f"   ✅ Test query successful (returned {len(contact_data)} rows)")
                    else:
                        print("   ⚠️  Test query returned None")
                except Exception as e:
                    # A query for non-existent contact is expected to succeed but return empty results
                    if "CNT-TEST" in str(e):
                        results["test_query"] = True
                        print("   ✅ Test query successful (no data for test contact, as expected)")
                    else:
                        print(f"   ⚠️  Test query failed: {str(e)}")

            else:
                results["status"] = "failed"
                print("   ❌ BigQuery connection failed")

        except Exception as e:
            results["status"] = "failed"
            results["error"] = str(e)
            print(f"   💥 BigQuery test failed: {str(e)}")

        return results

    def test_gemini_connection(self) -> Dict[str, Any]:
        """Test Gemini API connection with the new model."""
        print("\n🤖 Testing Gemini 2.5 Flash Connection...")

        results = {
            "status": "success",
            "model_configured": False,
            "api_key_present": False,
            "connection_test": False,
            "model_name": None,
            "generation_test": False,
        }

        try:
            # Check API key
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                results["api_key_present"] = True
                print(f"   ✅ Gemini API key present ({len(api_key)} characters)")
            else:
                results["status"] = "failed"
                print("   ❌ Gemini API key not found in environment")
                return results

            # Create Gemini processor with config
            gemini_config = self.config_loader.get_gemini_config()
            gemini_processor = create_gemini_processor(config=gemini_config)

            if gemini_processor.model:
                results["model_configured"] = True
                results["model_name"] = gemini_processor.model_name
                print(f"   ✅ Gemini model configured: {gemini_processor.model_name}")

                # Print generation config if available
                if gemini_processor.generation_config:
                    print(f"   ⚙️  Generation config: {gemini_processor.generation_config}")

                # Test connection
                if gemini_processor.test_connection():
                    results["connection_test"] = True
                    print("   ✅ Gemini API connection test successful")

                    # Test actual generation
                    try:
                        test_prompt = """
                        Please provide a brief test response to confirm the API is working.
                        Respond with: "Gemini 2.5 Flash is working correctly."
                        """

                        response = gemini_processor.generate_insights(test_prompt)
                        if response:
                            results["generation_test"] = True
                            print(f"   ✅ Test generation successful")
                            print(f"   📝 Response: {response[:100]}...")
                        else:
                            print("   ⚠️  Test generation returned empty response")

                    except Exception as e:
                        print(f"   ⚠️  Test generation failed: {str(e)}")
                else:
                    results["status"] = "failed"
                    print("   ❌ Gemini API connection test failed")
            else:
                results["status"] = "failed"
                print("   ❌ Failed to configure Gemini model")

        except Exception as e:
            results["status"] = "failed"
            results["error"] = str(e)
            print(f"   💥 Gemini test failed: {str(e)}")

        return results

    def test_openai_connection(self) -> Dict[str, Any]:
        """Test OpenAI API connection."""
        print("\n🤖 Testing OpenAI Connection...")

        results = {
            "status": "success",
            "model_configured": False,
            "api_key_present": False,
            "connection_test": False,
            "model_name": None,
            "generation_test": False,
        }

        try:
            # Check API key
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                results["api_key_present"] = True
                print(f"   ✅ OpenAI API key present ({len(api_key)} characters)")
            else:
                results["status"] = "failed"
                print("   ❌ OpenAI API key not found in environment")
                return results

            # Create OpenAI processor with config
            from ai_processing.openai_processor import create_openai_processor

            openai_config = self.config_loader.get_openai_config()
            openai_processor = create_openai_processor(config=openai_config)

            if openai_processor.client:
                results["model_configured"] = True
                results["model_name"] = openai_processor.model_name
                print(f"   ✅ OpenAI model configured: {openai_processor.model_name}")

                # Print generation config if available
                if openai_processor.generation_config:
                    print(f"   ⚙️  Generation config: {openai_processor.generation_config}")

                # Test connection
                connection_test = openai_processor.test_connection()
                if connection_test["connected"]:
                    results["connection_test"] = True
                    print("   ✅ OpenAI API connection test successful")
                    if "response" in connection_test:
                        print(f"   📝 Test response: {connection_test['response']}")

                    # Test actual generation with sample data
                    try:
                        import pandas as pd

                        test_data = pd.DataFrame([{"test": "sample data for generation test"}])

                        response = openai_processor.generate_insights(
                            system_prompt="You are a helpful assistant. Respond briefly to confirm the API is working.",
                            context_content="This is a test context.",
                            member_data=test_data,
                        )

                        if response:
                            results["generation_test"] = True
                            print(f"   ✅ Test generation successful")
                            print(f"   📝 Response: {response[:100]}...")
                        else:
                            print("   ⚠️  Test generation returned empty response")

                    except Exception as e:
                        print(f"   ⚠️  Test generation failed: {str(e)}")
                else:
                    results["status"] = "failed"
                    print("   ❌ OpenAI API connection test failed")
                    if connection_test.get("error"):
                        print(f"   📋 Error: {connection_test['error']}")
            else:
                results["status"] = "failed"
                print("   ❌ Failed to configure OpenAI client")

        except Exception as e:
            results["status"] = "failed"
            results["error"] = str(e)
            print(f"   💥 OpenAI test failed: {str(e)}")

        return results

    def test_airtable_connection(self) -> Dict[str, Any]:
        """Test Airtable API connection."""
        print("\n📊 Testing Airtable Connection...")

        results = {
            "status": "success",
            "api_key_present": False,
            "enhanced_writer": False,
            "structured_writer": False,
            "config_valid": False,
        }

        try:
            # Check API key
            api_key = os.getenv("AIRTABLE_API_KEY")
            if api_key:
                results["api_key_present"] = True
                print(f"   ✅ Airtable API key present ({len(api_key)} characters)")
            else:
                print("   ⚠️  Airtable API key not found (optional for basic functionality)")
                return results

            # Test Airtable configuration
            airtable_config = self.config_loader.get_airtable_config()
            if airtable_config:
                results["config_valid"] = True
                print("   ✅ Airtable configuration loaded")

                # Test enhanced Airtable writer
                try:
                    enhanced_writer = create_enhanced_airtable_writer()
                    if enhanced_writer.test_connection():
                        results["enhanced_writer"] = True
                        print("   ✅ Enhanced Airtable writer connection successful")
                    else:
                        print("   ❌ Enhanced Airtable writer connection failed")
                except Exception as e:
                    print(f"   ❌ Enhanced Airtable writer error: {str(e)}")

                # Test structured Airtable writer
                try:
                    if "structured_insight" in airtable_config:
                        structured_writer = create_structured_airtable_writer(airtable_config)
                        if structured_writer.test_connection():
                            results["structured_writer"] = True
                            print("   ✅ Structured Airtable writer connection successful")
                        else:
                            print("   ❌ Structured Airtable writer connection failed")
                    else:
                        print("   ⚠️  No structured insight configuration found")
                except Exception as e:
                    print(f"   ❌ Structured Airtable writer error: {str(e)}")
            else:
                print("   ❌ No Airtable configuration found")

        except Exception as e:
            results["status"] = "failed"
            results["error"] = str(e)
            print(f"   💥 Airtable test failed: {str(e)}")

        return results

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all API connection tests."""
        print("🚀 API Connection Test Suite")
        print("=" * 60)

        all_results = {}

        # Run all tests
        all_results["environment"] = self.test_environment_variables()
        all_results["configuration"] = self.test_configuration_loading()
        all_results["bigquery"] = self.test_bigquery_connection()

        # Test AI providers (based on configuration)
        ai_provider = self.config_loader.get_ai_provider()
        if ai_provider.lower() == "openai":
            all_results["openai"] = self.test_openai_connection()
            # Also test Gemini as backup option
            all_results["gemini"] = self.test_gemini_connection()
        else:
            all_results["gemini"] = self.test_gemini_connection()
            # Also test OpenAI as alternative option
            all_results["openai"] = self.test_openai_connection()

        all_results["airtable"] = self.test_airtable_connection()

        # Summary
        print("\n" + "=" * 60)
        print("📊 Test Summary")
        print("=" * 60)

        total_tests = 0
        passed_tests = 0

        for test_name, result in all_results.items():
            total_tests += 1
            status = result.get("status", "unknown")
            if status == "success":
                passed_tests += 1
                print(f"✅ {test_name.title()}: PASSED")
            else:
                print(f"❌ {test_name.title()}: FAILED")
                if "error" in result:
                    print(f"   Error: {result['error']}")

        print(f"\n📈 Results: {passed_tests}/{total_tests} tests passed")

        if passed_tests == total_tests:
            print("🎉 All tests PASSED! Your API connections are ready.")
        else:
            print("⚠️  Some tests failed. Check the details above.")

        return all_results


def main():
    """Main test function."""
    # Change to the correct directory for running tests
    test_dir = Path(__file__).parent.parent
    os.chdir(test_dir)

    tester = APIConnectionTester()
    results = tester.run_all_tests()

    # Return appropriate exit code
    failed_tests = [name for name, result in results.items() if result.get("status") != "success"]
    return 0 if not failed_tests else 1


if __name__ == "__main__":
    exit(main())
