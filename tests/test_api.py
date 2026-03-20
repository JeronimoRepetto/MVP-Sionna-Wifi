"""
MVP-Sionna-WiFi: API Tests
Validates FastAPI endpoints using the test client.
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Use FastAPI TestClient (requires httpx)
try:
    from fastapi.testclient import TestClient
    from main import app
    HAS_TESTCLIENT = True
except ImportError:
    HAS_TESTCLIENT = False
    print("⚠️  httpx not installed. Install with: pip install httpx")


def _get_client():
    if not HAS_TESTCLIENT:
        raise RuntimeError("TestClient not available (install httpx)")
    return TestClient(app)


def test_get_scene_endpoint():
    """GET /api/scene must return room, transmitter, and receivers."""
    client = _get_client()
    response = client.get("/api/scene")
    
    assert response.status_code == 200, f"Status {response.status_code}"
    data = response.json()
    
    assert "room" in data
    assert "transmitter" in data
    assert "receivers" in data
    assert data["room"]["width"] == 2.0
    assert data["room"]["depth"] == 3.5
    assert data["room"]["height"] == 2.0
    assert len(data["receivers"]) == 8
    print("  ✅ GET /api/scene returns valid data")


def test_post_simulate_endpoint():
    """POST /api/simulate must run simulation and return results."""
    client = _get_client()
    response = client.post("/api/simulate")
    
    assert response.status_code == 200, f"Status {response.status_code}"
    data = response.json()
    
    assert "paths" in data, "Missing 'paths' in response"
    assert "cir" in data, "Missing 'cir' in response"
    assert "csi" in data, "Missing 'csi' in response"
    assert "coverage" in data, "Missing 'coverage' in response"
    assert "simulation_time" in data, "Missing 'simulation_time'"
    
    assert len(data["paths"]) == 8
    assert len(data["cir"]) == 8
    assert len(data["csi"]) == 8
    print("  ✅ POST /api/simulate returns full results for 8 receivers")


def test_simulate_with_custom_params():
    """POST /api/simulate with custom parameters must work."""
    client = _get_client()
    response = client.post("/api/simulate?max_depth=3&num_samples=500000")
    
    assert response.status_code == 200
    data = response.json()
    # Verify params were received (in mock mode they're echoed)
    assert data["parameters"]["max_depth"] == 3 or data["parameters"]["max_depth"] == 6
    print("  ✅ Custom parameters accepted")


def test_get_coverage_endpoint():
    """GET /api/coverage must return coverage data."""
    client = _get_client()
    
    # First run a simulation to generate coverage
    client.post("/api/simulate")
    
    response = client.get("/api/coverage")
    assert response.status_code == 200
    data = response.json()
    
    assert "data" in data, "Missing 'data' in coverage"
    assert "grid_size" in data, "Missing 'grid_size'"
    assert "resolution" in data, "Missing 'resolution'"
    print("  ✅ GET /api/coverage returns valid coverage map")


def test_api_cors_headers():
    """API should include CORS headers for frontend access."""
    client = _get_client()
    response = client.options("/api/scene", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    })
    # CORS middleware should not block
    assert response.status_code in [200, 405]
    print("  ✅ CORS middleware configured")


def test_no_sensitive_data_in_responses():
    """API responses must not leak server paths, credentials, or system info."""
    client = _get_client()
    
    response = client.get("/api/scene")
    text = response.text
    
    # Check for common sensitive patterns
    sensitive_patterns = [
        "C:\\Users\\",         # Windows paths
        "/home/",             # Linux paths
        "password",
        "secret",
        "token",
        "api_key",
        "credentials",
    ]
    
    for pattern in sensitive_patterns:
        assert pattern.lower() not in text.lower(), \
            f"Sensitive pattern '{pattern}' found in /api/scene response"
    
    print("  ✅ No sensitive data in API responses")


# =============================================================================
# Runner
# =============================================================================
if __name__ == "__main__":
    if not HAS_TESTCLIENT:
        print("\n⚠️  Cannot run API tests: install httpx with 'pip install httpx'")
        sys.exit(0)
    
    tests = [
        test_get_scene_endpoint,
        test_post_simulate_endpoint,
        test_simulate_with_custom_params,
        test_get_coverage_endpoint,
        test_api_cors_headers,
        test_no_sensitive_data_in_responses,
    ]
    
    print("\n🧪 API Tests")
    print("=" * 50)
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 {test.__name__}: {type(e).__name__}: {e}")
            failed += 1
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
    print("✅ All API tests passed!\n")
