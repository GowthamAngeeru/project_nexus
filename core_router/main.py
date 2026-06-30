import time
import os
import grpc
from concurrent import futures
import logging
import uuid
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

import nexus_pb2
import nexus_pb2_grpc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SemanticRouter-Qdrant")

logger.info("🧠 Loading local embedding model (all-MiniLM-L6-v2)...")

embedder = SentenceTransformer('all-MiniLM-L6-v2')

ROUTING_THRESHOLD = float(os.getenv("ROUTING_THRESHOLD", "0.65"))


logger.info("🔌 Connecting to Qdrant Vector Database...")
qdrant = QdrantClient("http://127.0.0.1:6333")
COLLECTION_NAME = "routing_anchors"

if not qdrant.collection_exists(collection_name=COLLECTION_NAME):
    logger.info("🏗️ Creating Qdrant collection and injecting baseline semantic anchors...")
    qdrant.create_collection(
        collection_name = COLLECTION_NAME,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )

    anchors = [
        {"intent": "COGNITIVE_SWARM", "text": "Deploy a kubernetes cluster with a rust backend"},
        {"intent": "COGNITIVE_SWARM", "text": "Write a docker compose file for a microservice architecture"},
        {"intent": "COGNITIVE_SWARM", "text": "Design a highly available database schema for postgres"},
        {"intent": "LOCAL_FAST_LLM", "text": "Hello, how are you?"},
        {"intent": "LOCAL_FAST_LLM", "text": "What is the capital of France?"},
        {"intent": "LOCAL_FAST_LLM", "text": "Can you summarize this paragraph briefly?"}
    ]

    points =[
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedder.encode(item["text"]).tolist(),
            payload = {"intent":item["intent"], "text":item["text"]}
        )
        for item in anchors
    ]

    qdrant.upsert(collection_name =  COLLECTION_NAME, points=points)


class RouterService(nexus_pb2_grpc.RouterServiceServicer):

    def RouteTask(self, request, context):
        start_time = time.time()
        prompt = request.prompt

        logger.info(f"📥 Analyzing Prompt: '{prompt[:50]}...'")

        query_vector = embedder.encode(prompt).tolist()

        search_result = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=1
        ).points

        if search_result and search_result[0].score > ROUTING_THRESHOLD:
            selected_route = search_result[0].payload["intent"]
            confidence = search_result[0].score
            logger.info(f"High-confidence route: {selected_route} ({confidence:.2f})")

        else:
            selected_route = "LOCAL_FAST_LLM"
            confidence = search_result[0].score if search_result else 0.0
            logger.warning(f"Low-confidence fallback to LOCAL_FAST_LLM ({confidence:.2f})")

        execution_time_ms = (time.time() - start_time) * 1000
        
        logger.info(f"🚦 Qdrant Route: [{selected_route}] | Confidence: {confidence:.2f} | Latency: {execution_time_ms:.2f}ms")

        return nexus_pb2.RouterResponse(
            status="success",
            selected_route=selected_route,
            complexity_score=float(confidence),
            execution_time_ms=execution_time_ms
        )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    nexus_pb2_grpc.add_RouterServiceServicer_to_server(RouterService(), server)
    server.add_insecure_port('[::]:8001')
    
    logger.info("🟢 Qdrant-Powered ML gRPC Router listening on TCP Port 8001...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()