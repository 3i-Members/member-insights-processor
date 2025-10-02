#!/usr/bin/env python3
"""
Test Runner for Member Insights Processor

This script runs all test suites and provides a comprehensive test report.
"""

import unittest
import sys
import os
import time
from pathlib import Path
from io import StringIO

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class ColoredTestResult(unittest.TextTestResult):
    """Test result class with colored output."""
    
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.success_count = 0
        self.verbosity = verbosity
        
    def addSuccess(self, test):
        super().addSuccess(test)
        self.success_count += 1
        if self.verbosity > 1:
            self.stream.write("✅ ")
            self.stream.writeln(self.getDescription(test))
        else:
            self.stream.write("✅")
            
    def addError(self, test, err):
        super().addError(test, err)
        if self.verbosity > 1:
            self.stream.write("❌ ")
            self.stream.writeln(self.getDescription(test))
        else:
            self.stream.write("❌")
            
    def addFailure(self, test, err):
        super().addFailure(test, err)
        if self.verbosity > 1:
            self.stream.write("❌ ")
            self.stream.writeln(self.getDescription(test))
        else:
            self.stream.write("❌")
            
    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if self.verbosity > 1:
            self.stream.write("⏭️  ")
            self.stream.writeln(f"{self.getDescription(test)} (skipped: {reason})")
        else:
            self.stream.write("⏭️ ")


class ColoredTestRunner(unittest.TextTestRunner):
    """Test runner with colored output."""
    
    resultclass = ColoredTestResult
    
    def _makeResult(self):
        return self.resultclass(self.stream, self.descriptions, self.verbosity)


def discover_and_run_tests(test_dir: Path, pattern: str = "test_*.py", verbosity: int = 2):
    """
    Discover and run all tests in the given directory.
    
    Args:
        test_dir: Directory containing test files
        pattern: Pattern to match test files
        verbosity: Test verbosity level
        
    Returns:
        tuple: (success, results)
    """
    # Discover tests
    loader = unittest.TestLoader()
    suite = loader.discover(str(test_dir), pattern=pattern, top_level_dir=str(test_dir.parent))
    
    # Run tests
    runner = ColoredTestRunner(verbosity=verbosity, stream=sys.stdout)
    result = runner.run(suite)
    
    return result.wasSuccessful(), result


def run_specific_test_file(test_file: Path, verbosity: int = 2):
    """
    Run a specific test file.
    
    Args:
        test_file: Path to the test file
        verbosity: Test verbosity level
        
    Returns:
        tuple: (success, results)
    """
    # Import the test module
    import importlib.util
    spec = importlib.util.spec_from_file_location("test_module", test_file)
    test_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test_module)
    
    # Load tests from module
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(test_module)
    
    # Run tests
    runner = ColoredTestRunner(verbosity=verbosity, stream=sys.stdout)
    result = runner.run(suite)
    
    return result.wasSuccessful(), result


def print_test_summary(results, test_name: str, duration: float):
    """Print a summary of test results."""
    print(f"\n📊 {test_name} Summary:")
    print(f"   ⏱️  Duration: {duration:.2f}s")
    print(f"   🧪 Tests run: {results.testsRun}")
    print(f"   ✅ Successes: {getattr(results, 'success_count', results.testsRun - len(results.failures) - len(results.errors))}")
    print(f"   ❌ Failures: {len(results.failures)}")
    print(f"   💥 Errors: {len(results.errors)}")
    print(f"   ⏭️  Skipped: {len(results.skipped)}")
    
    if results.failures:
        print(f"\n📋 Failures:")
        for test, traceback in results.failures:
            print(f"   • {test}")
    
    if results.errors:
        print(f"\n📋 Errors:")
        for test, traceback in results.errors:
            print(f"   • {test}")


def main():
    """Main test runner function."""
    print("🚀 Member Insights Processor Test Suite")
    print("=" * 60)
    
    # Change to the correct directory
    test_dir = Path(__file__).parent
    project_dir = test_dir.parent
    os.chdir(project_dir)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Run Member Insights Processor tests")
    parser.add_argument("--test", help="Run specific test file")
    parser.add_argument("--pattern", default="test_*.py", help="Pattern to match test files")
    parser.add_argument("--verbose", "-v", action="count", default=1, help="Increase verbosity")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet output")
    parser.add_argument("--components-only", action="store_true", help="Run only component tests")
    parser.add_argument("--integration-only", action="store_true", help="Run only integration tests")
    
    args = parser.parse_args()
    
    verbosity = 0 if args.quiet else min(args.verbose + 1, 2)
    
    overall_success = True
    total_duration = 0
    test_results = []
    
    try:
        if args.test:
            # Run specific test file
            test_file = test_dir / args.test
            if not test_file.exists():
                test_file = test_dir / f"{args.test}.py"
            
            if not test_file.exists():
                print(f"❌ Test file not found: {args.test}")
                return 1
            
            print(f"🧪 Running specific test: {test_file.name}")
            print("-" * 40)
            
            start_time = time.time()
            success, results = run_specific_test_file(test_file, verbosity)
            duration = time.time() - start_time
            
            print_test_summary(results, test_file.stem, duration)
            overall_success = success
            total_duration = duration
            
        else:
            # Run all tests or filtered tests
            test_files = []
            
            if args.components_only:
                test_files = ["test_components.py", "test_null_handling.py"]
                print("🧪 Running Component Tests Only")
            elif args.integration_only:
                test_files = ["test_with_env.py", "test_structured_insights.py"]
                print("🧪 Running Integration Tests Only")
            else:
                # Run all tests
                test_files = [f.name for f in test_dir.glob(args.pattern) if f.is_file() and f.name != "test_runner.py"]
                print("🧪 Running All Tests")
            
            if not test_files:
                print("❌ No test files found")
                return 1
            
            print(f"📁 Found {len(test_files)} test file(s)")
            print("-" * 40)
            
            for test_file in test_files:
                test_path = test_dir / test_file
                
                print(f"\n🔬 Running {test_file}...")
                
                start_time = time.time()
                success, results = run_specific_test_file(test_path, verbosity)
                duration = time.time() - start_time
                
                test_results.append((test_file, success, results, duration))
                total_duration += duration
                
                if not success:
                    overall_success = False
                
                print_test_summary(results, test_file, duration)
                
                if not success and args.verbose < 2:
                    print(f"\n💡 Run with -vv for detailed error information")
        
        # Print overall summary
        print("\n" + "=" * 60)
        print("📊 Overall Test Summary")
        print("=" * 60)
        
        if test_results:
            total_tests = sum(r[2].testsRun for r in test_results)
            total_failures = sum(len(r[2].failures) for r in test_results)
            total_errors = sum(len(r[2].errors) for r in test_results)
            total_skipped = sum(len(r[2].skipped) for r in test_results)
            
            print(f"⏱️  Total Duration: {total_duration:.2f}s")
            print(f"📁 Test Files: {len(test_results)}")
            print(f"🧪 Total Tests: {total_tests}")
            print(f"✅ Passed: {total_tests - total_failures - total_errors}")
            print(f"❌ Failed: {total_failures + total_errors}")
            print(f"⏭️  Skipped: {total_skipped}")
            
            print(f"\n📋 Test File Results:")
            for test_file, success, results, duration in test_results:
                status = "✅ PASS" if success else "❌ FAIL"
                print(f"   {status} {test_file} ({duration:.2f}s)")
        
        if overall_success:
            print(f"\n🎉 All tests PASSED!")
            return 0
        else:
            print(f"\n💥 Some tests FAILED!")
            return 1
            
    except KeyboardInterrupt:
        print(f"\n⚠️  Tests interrupted by user")
        return 130
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit(main()) 