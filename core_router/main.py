from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import time
import os
import numpy as np
from openai import AsyncOpenAI

if not os.environ.get("OPENAI_API_KEY"):
    print("🚨 WARNING: OPENAI_API_KEY environment variable not found!")

app = FastAPI(title="Project Nexus: Core Router (Semantic RouteLLM Layer)")

client=AsyncOpenAI()

class RouterRequest(BaseModel):
    user_id:str
    prompt:str

class RouterResponse(BaseModel):
    status:str
    selected_route:str
    complexity_score:float
    execution_time_ms:float

COMPLEX_ANCHOR_TEXT = "I need to architect a scalable system, debug a severe race condition, write deployment YAML, design a database schema, and orchestrate a Kubernetes microservices cluster."

ANCHOR_EMBEDDING = None

async def get_embedding(text:str)-> list[float]:
    """Calls OpenAI's embedding model to convert text into a 1536-dimensional vector."""
    response = await client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def calculate_cosine_similarity(vec1: list[float], vec2:list[float]) -> float:
    """Mathematically compares two vectors. 1.0 is identical, 0.0 is completely unrelated."""

    dot_product = np.dot(vec1, vec2)
    norm_v1 = np.linalg.norm(vec1)
    norm_v2 = np.linalg.norm(vec2)

    return dot_product/ (norm_v1 * norm_v2)

@app.post("/api/v1/route", response_model=RouterResponse)
async def route_request(request:RouterRequest):
    global ANCHOR_EMBEDDING
    start_time = time.time()

    try:
        if ANCHOR_EMBEDDING is None:
            print("⚙️ Calibrating Semantic Anchor Matrix...")
            ANCHOR_EMBEDDING = await get_embedding(COMPLEX_ANCHOR_TEXT)

        user_embedding = await get_embedding(request.prompt)

        complexity = calculate_cosine_similarity(user_embedding, ANCHOR_EMBEDDING)

        if complexity >= 0.35:
            selected_route = "cognitive_agent_swarm"
        else:
            selected_route = "local_fast_llm"
            
        execution_time = (time.time() - start_time) * 1000

        print(f"🎯 ROUTER: Prompt graded {complexity:.2f} -> Routed to [{selected_route.upper()}]")
        
        return RouterResponse(
            status="success",
            selected_route=selected_route,
            complexity_score=complexity,
            execution_time_ms=execution_time
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)