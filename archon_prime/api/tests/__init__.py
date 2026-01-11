"""
ARCHON PRIME API Test Suite

Phase 6C: Hardening - Proving reliability under pressure.

Test Categories:
1. Unit tests - Individual component verification
2. Integration tests - Cross-component flows
3. End-to-end tests - Complete execution traces
4. Failure tests - Recovery and resilience
5. Load tests - Performance under stress

Test Files:
- conftest.py: Shared fixtures (database, users, profiles, mocks)
- test_e2e_signal_flow.py: End-to-end signal flow validation
- test_failure_modes.py: Failure simulation and recovery
- test_load_profile.py: Performance benchmarks

Run Commands:
    # All tests
    pytest tests/ -v

    # E2E tests only
    pytest tests/test_e2e_signal_flow.py -v

    # Failure tests only
    pytest tests/test_failure_modes.py -v

    # Benchmarks only
    pytest tests/test_load_profile.py -v -m benchmark

    # With coverage
    pytest tests/ --cov=archon_prime.api --cov-report=html
"""
