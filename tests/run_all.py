"""
MVP-Sionna-WiFi: Test Runner
Runs all test suites and reports results.
Usage: python tests/run_all.py
"""

import subprocess
import sys
import os

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)

test_files = [
    "test_config.py",
    "test_pose_library.py",
    "test_animation.py",
    "test_scene_loader.py",
    "test_simulation.py",
    "test_api.py",
]

def main():
    print("\n" + "=" * 60)
    print("  MVP-Sionna-WiFi — Full Test Suite")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    
    for test_file in test_files:
        filepath = os.path.join(TEST_DIR, test_file)
        if not os.path.exists(filepath):
            print(f"\n⚠️  {test_file} not found, skipping")
            continue
        
        result = subprocess.run(
            [sys.executable, filepath],
            cwd=PROJECT_DIR,
            capture_output=False,
        )
        
        if result.returncode == 0:
            total_passed += 1
        else:
            total_failed += 1
    
    print("\n" + "=" * 60)
    print(f"  Final: {total_passed} suites passed, {total_failed} failed")
    print("=" * 60 + "\n")
    
    sys.exit(1 if total_failed > 0 else 0)


if __name__ == "__main__":
    main()
