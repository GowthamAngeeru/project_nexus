import time
import grpc
from concurrent import futures
import logging
from typing import TypedDict, Annotated
import operator
import os
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

import nexus_pb2
import nexus_pb2_grpc

import evaluation_pb2
import evaluation_pb2_grpc

load_dotenv()

EVALUATION_URL = os.getenv("EVALUATION_URL", "http://127.0.0.1:8003")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger =logging.getLogger("CognitiveSwarm-gRPC")


class AgentState(TypedDict):
    messages:Annotated[list,operator.add]
    next_agent: str
    final_output: str

llm =ChatOpenAI(model="gpt-3.5-turbo", temperature=0.2)

def supervisor_agent(state: AgentState):
    prompt = state['messages'][0].content
    logger.info("🧠 Supervisor AI is analyzing the task intent...")
    
    # Smarter intent routing
    sys_msg = SystemMessage(content="""
    You are the Swarm Supervisor. Route the user's prompt to the correct specialized agent.
    - If the user explicitly asks to WRITE, DEPLOY, or CONFIGURE infrastructure (Docker, K8s, Terraform): output EXACTLY 'devops_agent'
    - If the user explicitly asks to WRITE software, scripts, or algorithms: output EXACTLY 'coder_agent'
    - If the user is asking HOW to do something, wants to LEARN, or needs an EXPLANATION/ARCHITECTURE: output EXACTLY 'tech_lead_agent'
    
    Output nothing else but the exact agent name.
    """)
    
    response = llm.invoke([sys_msg, HumanMessage(content=prompt)])
    decision = response.content.strip()
    
    # Fallback safety
    if decision not in ["devops_agent", "coder_agent", "tech_lead_agent"]:
        decision = "tech_lead_agent"
        
    logger.info(f"🔀 Supervisor Decision: Routing to [{decision}]")
    return {"next_agent": decision}

def coder_agent(state: AgentState):
    prompt = state['messages'][0].content
    sys_msg = SystemMessage(content="You are an elite Staff Software Engineer. Write clean, modular code. Output ONLY code.")
    response = llm.invoke([sys_msg, HumanMessage(content=prompt)])
    return {"final_output": response.content, "next_agent": "END"}

def devops_agent(state: AgentState):
    prompt = state['messages'][0].content
    sys_msg = SystemMessage(content="You are a Principal DevOps Engineer. Write strictly valid Docker, Kubernetes, or Terraform configurations. Output ONLY infrastructure code.")
    response = llm.invoke([sys_msg, HumanMessage(content=prompt)])
    return {"final_output": response.content, "next_agent": "END"}

def tech_lead_agent(state: AgentState):
    prompt = state['messages'][0].content
    sys_msg = SystemMessage(content="You are a Principal Tech Lead. Explain concepts, design architectures, and provide guidance clearly using Markdown formatting. Be concise and professional.")
    response = llm.invoke([sys_msg, HumanMessage(content=prompt)])
    return {"final_output": response.content, "next_agent": "END"}

workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_agent)
workflow.add_node("coder_agent", coder_agent)
workflow.add_node("devops_agent", devops_agent)
workflow.add_node("tech_lead_agent", tech_lead_agent) # Added new node

workflow.set_entry_point("supervisor")
workflow.add_conditional_edges(
    "supervisor",
    lambda x: x["next_agent"],
    {
        "coder_agent": "coder_agent", 
        "devops_agent": "devops_agent",
        "tech_lead_agent": "tech_lead_agent"
    }
)
workflow.add_edge("coder_agent", END)
workflow.add_edge("devops_agent", END)
workflow.add_edge("tech_lead_agent", END)

swarm_app = workflow.compile()

class SwarmService(nexus_pb2_grpc.SwarmServiceServicer):

    def ExecuteSwarmTask(self, request, context):
        start_time = time.time()
        logger.info(f"Swarm task starting. User: {request.user_id}")

        initial_state = {
            "messages": [HumanMessage(content=request.prompt)],
            "next_agent": "",
            "final_output": ""
        }

        agent_trace = []
        final_output = ""

        for s in swarm_app.stream(initial_state):
            agent_name = list(s.keys())[0]
            agent_trace.append(agent_name)
            if "final_output" in s[agent_name]:
                final_output = s[agent_name]["final_output"]

        execution_time_ms = (time.time() - start_time) * 1000

        # ── Evaluate the response ──────────────────────────────
        trust_score = 1.0
        verdict = "TRUSTED"
        reasoning = "Evaluation service unavailable"

        try:
            eval_channel = grpc.insecure_channel(
                EVALUATION_URL.replace("http://", "")
            )
            eval_stub = evaluation_pb2_grpc.EvaluationServiceStub(eval_channel)

            eval_response = eval_stub.EvaluateResponse(
                evaluation_pb2.EvaluationRequest(
                    question=request.prompt,
                    answer=final_output,
                    context="",  # No retrieved context in swarm path
                    agent_name=agent_trace[-1] if agent_trace else "unknown",
                    request_id=request.user_id,
                ),
                timeout=5.0
            )

            trust_score = eval_response.trust_score
            verdict = eval_response.verdict
            reasoning = eval_response.reasoning

            logger.info(
                f"Evaluation: trust={trust_score:.2f} "
                f"verdict={verdict} | {reasoning}"
            )

            if verdict == "HALLUCINATION_RISK":
                logger.warning(
                    f"HALLUCINATION_RISK detected in swarm response. "
                    f"trust={trust_score:.2f}"
                )

        except Exception as e:
            logger.warning(f"Evaluation service unreachable: {e}")

        # ── Return with evaluation metadata ───────────────────
        logger.info(
            f"Swarm complete. Trace: {agent_trace} | "
            f"Latency: {execution_time_ms:.2f}ms | "
            f"Trust: {trust_score:.2f}"
        )

        return nexus_pb2.SwarmResponse(
            status=f"success|trust={trust_score:.2f}|verdict={verdict}",
            agent_trace=agent_trace,
            final_output=final_output,
            execution_time_ms=execution_time_ms,
        )
    
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    nexus_pb2_grpc.add_SwarmServiceServicer_to_server(SwarmService(), server)
    server.add_insecure_port('[::]:8002')
    logger.info("🟢 LangGraph Cognitive Swarm listening on TCP Port 8002...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()