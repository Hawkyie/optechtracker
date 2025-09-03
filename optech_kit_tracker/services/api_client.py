import os
import requests


API_URL   = os.getenv("OPTECH_API_URL", "https://kit-tracker.peacemosquitto.workers.dev")
API_TOKEN = os.getenv("OPTECH_API_TOKEN", "63T-nAch05-p3W5-lIn60t")

def fetch_payloads():
    headers = {}
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"

    resp = requests.get(API_URL, headers=headers, timeout=8)
    resp.raise_for_status()
    data = resp.json()

    
    if isinstance(data, dict) and "results" in data:
        data = data["results"]
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []
