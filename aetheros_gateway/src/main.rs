use axum::{routing::post, Json, Router};
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use std::time::Instant;
use tower_http::cors::{Any, CorsLayer};

pub mod nexus {
    tonic::include_proto!("nexus");
}
use nexus::router_service_client::RouterServiceClient;
use nexus::swarm_service_client::SwarmServiceClient;
use nexus::{RouterRequest, SwarmRequest};

#[derive(Deserialize)]
struct IncomingRequest {
    user_id: String,
    prompt: String,
}

#[derive(Serialize)]
struct GatewayResponse {
    status: String,
    source: String,
    final_output: String,
    gateway_latency_ms: f64,
    routing_confidence: f32,
}

#[derive(Clone)]
struct AppState {
    redis_conn: redis::aio::MultiplexedConnection,
    router_client: RouterServiceClient<tonic::transport::Channel>,
    swarm_client: SwarmServiceClient<tonic::transport::Channel>,
}

async fn handle_request(
    axum::extract::State(data): axum::extract::State<AppState>,
    Json(req): Json<IncomingRequest>,
) -> Result<Json<GatewayResponse>, axum::http::StatusCode> {
    let start_time = Instant::now();
    let prompt = req.prompt.clone();
    let user_id = req.user_id.clone();
    let mut redis_conn = data.redis_conn.clone();

    // L2 Redis cache check
    let cached_output: redis::RedisResult<Option<String>> = redis_conn.get(&prompt).await;
    if let Ok(Some(output)) = cached_output {
        let latency = start_time.elapsed().as_secs_f64() * 1000.0;
        return Ok(Json(GatewayResponse {
            status: "success".to_string(),
            source: "L2_REDIS_CACHE".to_string(),
            final_output: output,
            gateway_latency_ms: latency,
            routing_confidence: 1.0,
        }));
    }

    // Use pre-built client from AppState — no new connection per request
    let mut router_client = data.router_client.clone();

    let router_res = match router_client
        .route_task(tonic::Request::new(RouterRequest {
            user_id: user_id.clone(),
            prompt: prompt.clone(),
        }))
        .await
    {
        Ok(response) => response.into_inner(),
        Err(e) => {
            eprintln!("Router gRPC error: {}", e);
            return Err(axum::http::StatusCode::INTERNAL_SERVER_ERROR);
        }
    };

    let source = router_res.selected_route.clone();
    let final_output: String;

    if router_res.selected_route == "COGNITIVE_SWARM" {
        // Use pre-built swarm client — no new connection per request
        let mut swarm_client = data.swarm_client.clone();

        let swarm_res = match swarm_client
            .execute_swarm_task(tonic::Request::new(SwarmRequest {
                user_id: user_id.clone(),
                prompt: prompt.clone(),
            }))
            .await
        {
            Ok(res) => res.into_inner(),
            Err(e) => {
                eprintln!("Swarm gRPC error: {}", e);
                return Err(axum::http::StatusCode::INTERNAL_SERVER_ERROR);
            }
        };
        final_output = swarm_res.final_output;
    } else {
        let ollama_url =
            std::env::var("OLLAMA_URL").unwrap_or_else(|_| "http://127.0.0.1:11434".to_string());

        let client = reqwest::Client::new();
        let payload = serde_json::json!({
            "model": "tinyllama",
            "messages": [
                {"role": "system", "content": "You are a fast, concise AI. Answer briefly."},
                {"role": "user", "content": &prompt}
            ],
            "stream": false
        });

        final_output = match client
            .post(format!("{}/api/chat", ollama_url))
            .json(&payload)
            .send()
            .await
        {
            Ok(response) => {
                if let Ok(json) = response.json::<serde_json::Value>().await {
                    json["message"]["content"]
                        .as_str()
                        .unwrap_or("Failed to parse Ollama response.")
                        .to_string()
                } else {
                    "Error parsing local LLM response.".to_string()
                }
            }
            Err(_) => "Local LLM unavailable. Is Ollama running?".to_string(),
        };
    }

    let _: redis::RedisResult<()> = redis_conn.set(&prompt, &final_output).await;
    let latency = start_time.elapsed().as_secs_f64() * 1000.0;

    Ok(Json(GatewayResponse {
        status: "success".to_string(),
        source,
        final_output,
        gateway_latency_ms: latency,
        routing_confidence: router_res.complexity_score,
    }))
}

#[tokio::main]
async fn main() {
    dotenvy::dotenv().ok();

    println!("Booting Nexus Gateway...");

    // Redis connection
    let redis_url =
        std::env::var("REDIS_URL").unwrap_or_else(|_| "redis://127.0.0.1:6379".to_string());
    let redis_client = redis::Client::open(redis_url).expect("Invalid Redis URL");
    let redis_conn = redis_client
        .get_multiplexed_async_connection()
        .await
        .expect("Redis connection failed");
    println!("Redis connected.");

    // Build gRPC clients ONCE at startup — reused across all requests
    let router_url =
        std::env::var("ROUTER_URL").unwrap_or_else(|_| "http://127.0.0.1:8001".to_string());
    let router_client = RouterServiceClient::connect(router_url.clone())
        .await
        .unwrap_or_else(|e| panic!("Cannot connect to router at {}: {}", router_url, e));
    println!("Router client connected: {}", router_url);

    let swarm_url =
        std::env::var("SWARM_URL").unwrap_or_else(|_| "http://127.0.0.1:8002".to_string());
    let swarm_client = SwarmServiceClient::connect(swarm_url.clone())
        .await
        .unwrap_or_else(|e| panic!("Cannot connect to swarm at {}: {}", swarm_url, e));
    println!("Swarm client connected: {}", swarm_url);

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let app = Router::new()
        .route("/api/v1/chat", post(handle_request))
        .layer(cors)
        .with_state(AppState {
            redis_conn,
            router_client, // ← passed into state
            swarm_client,  // ← passed into state
        });

    let port = std::env::var("PORT").unwrap_or_else(|_| "8080".to_string());
    let addr = format!("0.0.0.0:{}", port);
    println!("Gateway online: {}", addr);

    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
