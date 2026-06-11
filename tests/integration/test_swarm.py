import requests

SWARM_URL ="http://127.0.0.1:8002/api/v1/swarm/execute"

payload={
    "user_id":"nexus_admin",
    "prompt": "We have a kubernetes deadlock and need to configure a docker swarm."
}

print("🚀 FIRING DIRECT REQUEST TO COGNITIVE SWARM...\n")

try:
    response = requests.post(SWARM_URL, json=payload)
    data = response.json()

    print(f"Status: {data['status']}")
    print(f"Execution Time: {data['execution_time_ms']:.2f}ms\n")
    print("🤖 AGENT TRACE:")
    for step in data['agent_trace']:
        print(f"  -> {step}")
        
    print(f"\n✅ FINAL OUTPUT:\n{data['final_output']}")
except Exception as e:
    print(f"🚨 ERROR: {e}")