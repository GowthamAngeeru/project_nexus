import requests
import time

GATEWAY_URL = "http://127.0.0.1:8080/api/v1/generate"

payload = {
    "user_id": "nexus_ceo",
    "prompt": "I need you to architect a highly scalable database schema and deploy it using a docker swarm."
}

print("🚀 FIRING REQUEST AT THE RUST GATEWAY...\n")

start = time.time()

try:
    response = requests.post(GATEWAY_URL, json=payload)
    data = response.json()
    
    total_time = (time.time() - start) * 1000
    
    print(f"Status: {data['status']}")
    print(f"Source: {data['source']}")
    print(f"Gateway Latency: {data['latency_ms']}ms")
    print(f"Total Round Trip Time: {total_time:.2f}ms\n")
    print(f"✅ FINAL OUTPUT:\n{data['message']}")
    
except Exception as e:
    print(f"🚨 ERROR: {e}")