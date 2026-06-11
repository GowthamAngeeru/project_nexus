from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import time
import os
from typing import Annotated, Literal, TypedDict
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages


if not os.environ.get("OPENAI_API_KEY"):
    print("🚨 WARNING: OPENAI_API_KEY environment variable not found!")

app = FastAPI(title="Project Nexus: Cognitive Agent Swarm")

class SwarmRequest(BaseModel):
    user_id: str
    prompt: str

class SwarmResponse(BaseModel):
    status: str
    agent_trace: list[str]
    final_output: str
    execution_time_ms: float

class AgentState(TypedDict):
    messages:Annotated[list[BaseMessage], add_messages]
    next:str

llm= ChatOpenAI(model="gpt-4o-mini", temperature=0)

def devops_agent(state:AgentState):
    print("  -> [DevOps Agent]: Working...")
    prompt = "You are an elite DevOps architect. Provide a high-level infrastructure plan for the user's request. Keep it concise."
    response = llm.invoke([{"role":"system", "content":prompt}]+state["messages"])

    return {"messages":[AIMessage(content=response.content, name="DevOps")]}

def coder_agent(state: AgentState):
    print("  -> [Coder Agent]: Working...")
    prompt = "You are a Senior Systems Programmer. Look at the DevOps plan and write the YAML or code needed. Keep it very short."
    response = llm.invoke([{"role": "system", "content": prompt}] + state["messages"])
    return {"messages": [AIMessage(content=response.content, name="Coder")]}

def supervisor_agent(state:AgentState):
    print("  -> [Supervisor]: Evaluating State...")

    messages = state["messages"]

    if len(messages) == 1:
        return {"next": "DevOps"}
    elif messages[-1].name == "DevOps":
        return {"next": "Coder"}
    else:
        return {"next": "FINISH"}
    
workflow = StateGraph(AgentState)

workflow.add_node("Supervisor", supervisor_agent)
workflow.add_node("DevOps", devops_agent)
workflow.add_node("Coder", coder_agent)

workflow.set_entry_point("Supervisor")

workflow.add_conditional_edges(
    "Supervisor",
    lambda state: state["next"],
    {
        "DevOps": "DevOps",
        "Coder": "Coder",
        "FINISH": END
    }
)

workflow.add_edge("DevOps", "Supervisor")
workflow.add_edge("Coder", "Supervisor")

cognitive_engine = workflow.compile()

@app.post("/api/v1/swarm/execute", response_model=SwarmResponse)
async def trigger_swarm(request: SwarmRequest):
    start_time = time.time()
    print(f"🧬 SWARM ACTIVATED: Task from '{request.user_id}'")

    initial_state = {"messages": [HumanMessage(content=request.prompt)]}
    final_state = cognitive_engine.invoke(initial_state)

    trace=[]
    final_output = ""

    for msg in final_state["messages"]:
        if isinstance(msg, AIMessage) and msg.name:
            trace.append(f"[{msg.name} Agent]: Generated response.")
            final_output = msg.content
            
    execution_time = (time.time() - start_time) * 1000
    
    return SwarmResponse(
        status="success",
        agent_trace=trace,
        final_output=final_output,
        execution_time_ms=execution_time
    )

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8002)