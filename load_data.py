import requests
import json
import os

url = "http://localhost:8000/feature-engineering"

for i in range(1, 11):
    file_path = f'C:\\Users\\user\\Desktop\\optasia\\customer_dataset_{i:02d}.json'

    with open(file_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)
        response = requests.post(url, json=payload)
        
        resp_json = response.json()
        latency = resp_json.get("metrics", {}).get("request_latency_ms", "N/A")
        
        # Check if any customers in the file were skipped
        results = resp_json.get("results", [])
        errors = [r for r in results if r["status"] == "Skipped"]
        
        if not errors:
            print(f"File {i:02d}: OK | Latency: {latency}ms")
        else:
            print(f"File {i:02d}:  Skipped due to errors in vlidation")
