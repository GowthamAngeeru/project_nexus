import requests
import concurrent.futures
import time

URL = "http://127.0.0.1:8080/api/v1/generate"
PAYLOAD = {
    "user_id": "nexus_admin",
    "prompt": "How does Cortex-MQ prevent deadlocks?"
}

def fire_request(req_id):
    
    start = time.time()
    try:
        response = requests.post(URL, json=PAYLOAD)
        latency = time.time() - start
        data = response.json()

        status = response.status_code
        source = data.get('source', 'UNKNOWN')
        return f"Req {req_id:02d} | Status: {status} | Source: {source: <20} | Latency: {latency:.1f}ms"
    except Exception as e:
        return f"Req {req_id:02d} | Error: {e}"
    
if __name__ == "__main__":
    print("\n🚀 Firing 10 simultaneous requests at AetherOS Gateway...\n")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results =executor.map(fire_request, range(1, 11))

    for res in results:
        print(res)
    print("\n==================================================")