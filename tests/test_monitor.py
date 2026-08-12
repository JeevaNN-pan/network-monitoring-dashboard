"""
Basic unit tests for monitor.py using mocks - no real network access needed.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import monitor  # noqa: E402


def test_tcp_check_success():
    with patch("socket.create_connection") as mock_conn:
        mock_conn.return_value.__enter__.return_value = MagicMock()
        result = monitor._tcp_check("127.0.0.1", port=443)
    assert result.is_up is True
    assert result.method == "tcp:443"


def test_tcp_check_failure():
    with patch("socket.create_connection", side_effect=OSError):
        result = monitor._tcp_check("127.0.0.1", port=443)
    assert result.is_up is False
    assert result.latency_ms is None


def test_check_device_uses_tcp_for_tcp_prefix():
    with patch("monitor._tcp_check") as mock_tcp:
        mock_tcp.return_value = monitor.CheckResult(is_up=True, latency_ms=5.0, method="tcp:22")
        result = monitor.check_device("10.0.0.1", method="tcp:22")
    mock_tcp.assert_called_once_with("10.0.0.1", port=22)
    assert result.is_up is True


def test_check_device_falls_back_to_tcp_when_ping_fails():
    with patch("monitor._ping") as mock_ping, patch("monitor._tcp_check") as mock_tcp:
        mock_ping.return_value = monitor.CheckResult(is_up=False, latency_ms=None, method="icmp")
        mock_tcp.return_value = monitor.CheckResult(is_up=True, latency_ms=12.0, method="tcp:443")
        result = monitor.check_device("10.0.0.1", method="ping")
    mock_tcp.assert_called_once_with("10.0.0.1", port=443)
    assert result.is_up is True
