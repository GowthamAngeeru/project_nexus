import requests
import time

# 1. FIXED ENDPOINT
GATEWAY_URL = "http://127.0.0.1:8080/api/v1/chat"

payload = {
    "user_id": "nexus_ceo",
    "prompt": "I need you to architect a highly scalable database schema and deploy it using a docker swarm."
}

print("🚀 FIRING REQUEST AT THE RUST GATEWAY...\n")

start = time.time()

try:
    response = requests.post(GATEWAY_URL, json=payload)
    
    # This will print the actual error if the server fails, instead of silently dying
    response.raise_for_status() 
    
    data = response.json()
    total_time = (time.time() - start) * 1000
    
    # 2. FIXED DICTIONARY KEYS TO MATCH RUST STRUCT
    print(f"Status: {data['status']}")
    print(f"Source: {data['source']}")
    print(f"Routing Confidence: {data['routing_confidence']:.2f}")
    print(f"Gateway Latency: {data['gateway_latency_ms']:.2f}ms")
    print(f"Total Round Trip Time: {total_time:.2f}ms\n")
    print(f"✅ FINAL OUTPUT:\n{data['final_output']}")
    
except requests.exceptions.HTTPError as err:
    print(f"🚨 HTTP ERROR: {err} | Response: {response.text}")
except Exception as e:
    print(f"🚨 PARSE ERROR: {e}")