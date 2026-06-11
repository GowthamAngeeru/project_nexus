import requests
import json

ROUTER_URL = "http://127.0.0.1:8001/api/v1/route"

def test_prompt(test_name, user_id, prompt_text):
    print(f"\n🧪 RUNNING TEST: {test_name}")
    print(f"Prompt: '{prompt_text}'")

    payload = {
        "user_id": user_id,
        "prompt": prompt_text
    }

    try:
        response = requests.post(ROUTER_URL, json=payload)
        data = response.json()

        print(f"Status: {data['status']}")
        print(f"Complexity Score: {data['complexity_score']:.2f}")
        print(f"Selected Route:   [{data['selected_route'].upper()}]")
        print(f"Execution Time:   {data['execution_time_ms']:.2f}ms")

    except Exception as e:
        print(f"🚨 ERROR: {e}")

if __name__ == "__main__":
    print("==================================================")
    print("🚀 INITIATING ROUTELLM INTELLIGENCE TEST")
    print("==================================================")

    test_prompt(
        test_name="Simple General Knowledge",
        user_id="nexus_user_01",
        prompt_text="What is the capital of France?"
    )

    test_prompt(
        test_name="Complex Engineering Architecture",
        user_id="nexus_admin",
        prompt_text="I need you to architect a highly scalable database schema and deploy it using a docker swarm. We need to debug a severe race condition and potential deadlock in our production kubernetes cluster."
    )
    
    print("\n==================================================")