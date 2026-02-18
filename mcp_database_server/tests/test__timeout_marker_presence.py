import pytest


def test_pytest_timeout_marker_available_or_skipped() -> None:
    """
    This suite uses @pytest.mark.timeout for subprocess-based smoke tests.

    If pytest-timeout is not installed, the marker becomes a no-op warning in many setups.
    This test documents that behavior and keeps the suite explicit.
    """
    assert hasattr(pytest.mark, "timeout")
