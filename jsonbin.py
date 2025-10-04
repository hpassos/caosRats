import requests, os

BASE = os.getenv("JSONBIN_BASE", "https://api.jsonbin.io/v3/b")
BIN_ID = os.environ["JSONBIN_BIN_ID"]
KEY = os.environ["JSONBIN_KEY"]

HEADERS = {"X-Master-Key": KEY, "Content-Type": "application/json"}

def get_state():
    r = requests.get(f"{BASE}/{BIN_ID}/latest", headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get("record", {}) or {}

def put_state(state: dict):
    r = requests.put(f"{BASE}/{BIN_ID}", headers=HEADERS, json=state, timeout=20)
    r.raise_for_status()
    return r.json().get("record", state)
