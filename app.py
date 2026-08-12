"""
Network Monitoring Dashboard - FastAPI backend.

Polls a list of network devices (routers, switches, or any IP-reachable
host) on a schedule, records availability history in SQLite, and exposes
a small REST API consumed by the static dashboard in index.html.

Personal networking/automation lab project - see README.md for scope,
limitations and disclaimer.
"""

import threading
import time
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

import database
from monitor import check_device

BASE_DIR = Path(__file__).resolve().parent
DEVICES_FILE = BASE_DIR / "devices.yaml"
POLL_INTERVAL_SECONDS = 30

app = FastAPI(title="Network Monitoring Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_devices():
    with open(DEVICES_FILE, "r") as f:
        data = yaml.safe_load(f)
    return data.get("devices", [])


def poll_loop():
    """Background thread: checks every device on a fixed interval and
    writes the result to SQLite."""
    devices = load_devices()
    while True:
        for device in devices:
            result = check_device(device["ip"], device.get("check", "ping"))
            database.record_check(
                name=device["name"],
                ip=device["ip"],
                device_type=device.get("type", "unknown"),
                is_up=result.is_up,
                latency_ms=result.latency_ms,
            )
        time.sleep(POLL_INTERVAL_SECONDS)


@app.on_event("startup")
def startup():
    database.init_db()
    thread = threading.Thread(target=poll_loop, daemon=True)
    thread.start()


@app.get("/api/devices")
def get_devices():
    """Return the configured device inventory."""
    return load_devices()


@app.get("/api/status")
def get_status():
    """Return the latest known status for every device."""
    return database.get_latest_status()


@app.get("/api/history/{device_name}")
def get_history(device_name: str, limit: int = 100):
    """Return recent check history for a single device."""
    history = database.get_history(device_name, limit)
    if not history:
        raise HTTPException(status_code=404, detail=f"No history for '{device_name}'")
    return history


@app.get("/api/summary")
def get_summary():
    """Return uptime percentage and average latency per device."""
    return database.get_summary()


@app.get("/", response_class=HTMLResponse)
def dashboard():
    html_path = BASE_DIR / "index.html"
    return html_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
