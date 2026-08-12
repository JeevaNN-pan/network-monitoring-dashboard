"""
monitor.py - Availability checks for network devices.

Uses ICMP ping (via the OS ping utility) with a TCP "port open" check as
a fallback for hosts/networks where ICMP is filtered - a common situation
on real Cisco gear with ICMP ACLs, or on cloud security groups.
"""

import platform
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class CheckResult:
    is_up: bool
    latency_ms: Optional[float]
    method: str


def _now_ms() -> float:
    return time.perf_counter() * 1000


def _ping(ip: str, timeout_s: int = 1) -> CheckResult:
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_s * 1000), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout_s), ip]

    try:
        start = _now_ms()
        completed = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s + 2
        )
        latency = _now_ms() - start
        is_up = completed.returncode == 0
        return CheckResult(is_up=is_up, latency_ms=latency if is_up else None, method="icmp")
    except (subprocess.TimeoutExpired, OSError):
        return CheckResult(is_up=False, latency_ms=None, method="icmp")


def _tcp_check(ip: str, port: int = 443, timeout_s: int = 1) -> CheckResult:
    start = _now_ms()
    try:
        with socket.create_connection((ip, port), timeout=timeout_s):
            latency = _now_ms() - start
            return CheckResult(is_up=True, latency_ms=latency, method=f"tcp:{port}")
    except OSError:
        return CheckResult(is_up=False, latency_ms=None, method=f"tcp:{port}")


def check_device(ip: str, method: str = "ping") -> CheckResult:
    """Run a single availability check against a device.

    method: "ping" for ICMP, or "tcp:<port>" e.g. "tcp:22" for a TCP
    reachability check when ICMP is blocked or unavailable.
    """
    if method.startswith("tcp:"):
        port = int(method.split(":", 1)[1])
        return _tcp_check(ip, port=port)

    result = _ping(ip)
    if not result.is_up:
        # Fall back to a TCP check in case ICMP is filtered but the host
        # is still reachable - mirrors real-world firewall behaviour.
        return _tcp_check(ip, port=443)
    return result
