"""
Project Nexus — Evaluation Service

Scores agent responses for faithfulness, relevancy, 
and hallucination risk using RAGAS-inspired metrics.

Port: 8003 (gRPC)
"""

import os
import re
import time
import grpc
import logging
from concurrent import futures
from dataclasses import dataclass
from typing import Optional

from sentence_transformers import SentenceTransformer
import numpy as np

import evaluation_pb2
import evaluation_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("NexusEvaluator")

# Load embedding model once at startup
logger.info("Loading evaluation embedding model...")
embedder = SentenceTransformer('all-MiniLML6V2')
logger.info("Evaluation model ready.")


@dataclass
class EvaluationResult:
    faithfulness_score: float      # Does answer align with context? 0.0–1.0
    relevancy_score: float         # Is answer relevant to the question? 0.0–1.0
    hallucination_risk: float      # Probability of hallucination. 0.0–1.0
    trust_score: float             # Overall trust. 0.0–1.0
    verdict: str                   # TRUSTED / UNCERTAIN / HALLUCINATION_RISK
    reasoning: str                 # Why this verdict was reached


def compute_semantic_similarity(text_a: str, text_b: str) -> float:
    """Cosine similarity between two text embeddings."""
    if not text_a.strip() or not text_b.strip():
        return 0.0
    vec_a = embedder.encode(text_a, normalize_embeddings=True)
    vec_b = embedder.encode(text_b, normalize_embeddings=True)
    return float(np.dot(vec_a, vec_b))


def score_faithfulness(answer: str, context: str) -> float:
    """
    Measures whether the answer is grounded in the provided context.
    
    High score: answer semantically aligns with context.
    Low score: answer introduces information not in context (hallucination risk).
    
    If no context is provided, returns 0.5 (uncertain — no ground truth).
    """
    if not context.strip():
        return 0.5  # Cannot evaluate faithfulness without context

    return compute_semantic_similarity(answer, context)


def score_relevancy(answer: str, question: str) -> float:
    """
    Measures whether the answer actually addresses the question asked.
    
    High score: answer directly responds to the question.
    Low score: answer is off-topic or evasive.
    """
    return compute_semantic_similarity(answer, question)


def detect_hallucination_patterns(answer: str) -> tuple[float, list[str]]:
    """
    Rule-based hallucination detection for common AI failure patterns.
    
    Detects:
    - Confident assertions about specific facts (names, dates, numbers)
      that cannot be verified against context
    - Contradiction indicators
    - Hedging language that suggests uncertainty
    - Fabricated citations or references
    
    Returns: (risk_score, list_of_detected_patterns)
    """
    risk_factors = []
    risk_score = 0.0

    answer_lower = answer.lower()

    # Pattern 1: Specific numeric claims without context verification
    numeric_claims = re.findall(
        r'\b\d{4}\b|\b\d+\.?\d*\s*(?:percent|%|million|billion|thousand)\b',
        answer_lower
    )
    if len(numeric_claims) > 3:
        risk_score += 0.15
        risk_factors.append(f"Multiple specific numeric claims ({len(numeric_claims)} found)")

    # Pattern 2: Confident assertions about named entities
    confident_patterns = [
        r'\b(?:definitely|certainly|absolutely|always|never|guaranteed)\b',
        r'\b(?:the fact that|it is known that|studies show|research proves)\b',
    ]
    for pattern in confident_patterns:
        if re.search(pattern, answer_lower):
            risk_score += 0.10
            risk_factors.append(f"Overconfident assertion detected: '{pattern}'")

    # Pattern 3: Fabricated citation patterns
    citation_patterns = [
        r'\baccording to\s+[A-Z][a-z]+\s+(?:et al|study|research|report)\b',
        r'\b(?:source|citation|reference):\s*\[?\d+\]?\b',
    ]
    for pattern in citation_patterns:
        if re.search(pattern, answer, re.IGNORECASE):
            risk_score += 0.20
            risk_factors.append("Potential fabricated citation")

    # Pattern 4: Contradiction indicators
    contradiction_patterns = [
        r'\b(?:however|but|although|nevertheless).{0,50}(?:also|as well|additionally)\b',
    ]
    for pattern in contradiction_patterns:
        if re.search(pattern, answer_lower):
            risk_score += 0.05
            risk_factors.append("Internal contradiction pattern detected")

    # Pattern 5: Very short answers to complex questions (evasion)
    if len(answer.split()) < 10:
        risk_score += 0.10
        risk_factors.append("Suspiciously brief response")

    return min(risk_score, 1.0), risk_factors


def evaluate_response(
    question: str,
    answer: str,
    context: str,
    agent_name: str
) -> EvaluationResult:
    """
    Full RAGAS-inspired evaluation pipeline.
    """
    start = time.perf_counter()

    faithfulness = score_faithfulness(answer, context)
    relevancy = score_relevancy(answer, question)
    hallucination_risk, patterns = detect_hallucination_patterns(answer)

    # Trust score: weighted combination
    # Relevancy weighted highest — an irrelevant answer is always wrong
    # Faithfulness matters when context is provided
    # Hallucination risk is a direct penalty
    trust_score = (
        relevancy * 0.45 +
        faithfulness * 0.35 +
        (1.0 - hallucination_risk) * 0.20
    )
    trust_score = max(0.0, min(1.0, trust_score))

    # Verdict thresholds (calibrated against manual evaluation)
    if trust_score >= 0.75 and hallucination_risk < 0.25:
        verdict = "TRUSTED"
    elif trust_score >= 0.50 or hallucination_risk < 0.40:
        verdict = "UNCERTAIN"
    else:
        verdict = "HALLUCINATION_RISK"

    # Build reasoning explanation
    reasoning_parts = [
        f"Relevancy: {relevancy:.2f}",
        f"Faithfulness: {faithfulness:.2f}",
        f"Hallucination risk: {hallucination_risk:.2f}",
    ]
    if patterns:
        reasoning_parts.append(f"Risk patterns: {'; '.join(patterns[:2])}")

    elapsed_ms = (time.perf_counter() - start) * 1000

    logger.info(
        f"Evaluated [{agent_name}] | "
        f"trust={trust_score:.2f} | "
        f"verdict={verdict} | "
        f"latency={elapsed_ms:.1f}ms"
    )

    return EvaluationResult(
        faithfulness_score=faithfulness,
        relevancy_score=relevancy,
        hallucination_risk=hallucination_risk,
        trust_score=trust_score,
        verdict=verdict,
        reasoning=" | ".join(reasoning_parts),
    )


class EvaluationServicer(evaluation_pb2_grpc.EvaluationServiceServicer):

    def EvaluateResponse(self, request, context):
        result = evaluate_response(
            question=request.question,
            answer=request.answer,
            context=request.context,
            agent_name=request.agent_name,
        )

        return evaluation_pb2.EvaluationResponse(
            trust_score=result.trust_score,
            faithfulness_score=result.faithfulness_score,
            relevancy_score=result.relevancy_score,
            hallucination_risk=result.hallucination_risk,
            verdict=result.verdict,
            reasoning=result.reasoning,
        )

    def BatchEvaluate(self, request, context):
        results = []
        for item in request.items:
            result = evaluate_response(
                question=item.question,
                answer=item.answer,
                context=item.context,
                agent_name=item.agent_name,
            )
            results.append(evaluation_pb2.EvaluationResponse(
                trust_score=result.trust_score,
                faithfulness_score=result.faithfulness_score,
                relevancy_score=result.relevancy_score,
                hallucination_risk=result.hallucination_risk,
                verdict=result.verdict,
                reasoning=result.reasoning,
            ))

        return evaluation_pb2.BatchEvaluationResponse(results=results)


def serve():
    port = os.getenv("EVALUATION_PORT", "8003")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    evaluation_pb2_grpc.add_EvaluationServiceServicer_to_server(
        EvaluationServicer(), server
    )
    server.add_insecure_port(f'[::]:{port}')
    logger.info(f"Nexus Evaluation Service listening on port {port}")
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()