use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use dashmap::DashMap;
use reqwest::Client as HttpClient;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::env;
use std::time::{Duration, Instant};

#[derive(Deserialize)]
struct AIRequest {
    user_id: String,
    prompt: String,
}

#[derive(Serialize)]
struct GatewayResponse {
    status: String,
    source: String,
    message: String,
    latency_ms: u128,
}

struct AppState {
    rate_limiter: DashMap<String, (u32, Instant)>,
    semantic_cache: DashMap<String, (Vec<f32>, String)>,
    http_client: HttpClient,
    openai_key: String,
}

fn cosine_similarity(v1: &[f32], v2: &[f32]) -> f32 {
    let dot: f32 = v1.iter().zip(v2).map(|(a, b)| a * b).sum();
    let mag1: f32 = v1.iter().map(|a| a * a).sum::<f32>().sqrt();
    let mag2: f32 = v2.iter().map(|b| b * b).sum::<f32>().sqrt();
    if mag1 == 0.0 || mag2 == 0.0 {
        0.0
    } else {
        dot / (mag1 * mag2)
    }
}

async fn get_embedding(client: &HttpClient, key: &str, text: &str) -> Vec<f32> {
    let res = client
        .post("https://api.openai.com/v1/embeddings")
        .bearer_auth(key)
        .json(&json!({
            "input": text,
            "model": "text-embedding-3-small"
        }))
        .send()
        .await
        .expect("Failed to connect to OpenAI")
        .json::<serde_json::Value>()
        .await
        .expect("Failed to parse OpenAI response");

    res["data"][0]["embedding"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_f64().unwrap() as f32)
        .collect()
}

async fn process_prompt(
    req_body: web::Json<AIRequest>,
    state: web::Data<AppState>,
) -> impl Responder {
    let start_time = Instant::now();

    let now = Instant::now();
    let mut user_record = state
        .rate_limiter
        .entry(req_body.user_id.clone())
        .or_insert((0, now));
    if now.duration_since(user_record.value().1) > Duration::from_secs(10) {
        user_record.value_mut().0 = 0;
        user_record.value_mut().1 = now;
    }
    if user_record.value().0 >= 5 {
        return HttpResponse::TooManyRequests().json(GatewayResponse {
            status: "error".to_string(),
            source: "aetheros_shield".to_string(),
            message: "Rate limit exceeded.".to_string(),
            latency_ms: start_time.elapsed().as_millis(),
        });
    }
    user_record.value_mut().0 += 1;

    println!("🧠 Generating vector embedding for incoming request...");
    let user_embedding =
        get_embedding(&state.http_client, &state.openai_key, &req_body.prompt).await;

    for entry in state.semantic_cache.iter() {
        let (cached_vec, cached_answer) = entry.value();
        let similarity = cosine_similarity(&user_embedding, cached_vec);

        if similarity > 0.90 {
            println!(
                "⚡ SEMANTIC CACHE HIT (Score: {:.2}): Saving cluster resources!",
                similarity
            );
            return HttpResponse::Ok().json(GatewayResponse {
                status: "success".to_string(),
                source: "l1_vector_cache".to_string(),
                message: cached_answer.clone(),
                latency_ms: start_time.elapsed().as_millis(),
            });
        }
    }

    println!("🔍 CACHE MISS: Asking Python Router (Port 8001) for directions...");

    let router_res = state
        .http_client
        .post("http://127.0.0.1:8001/api/v1/route")
        .json(&json!({ "user_id": req_body.user_id, "prompt": req_body.prompt }))
        .send()
        .await
        .unwrap()
        .json::<serde_json::Value>()
        .await
        .unwrap();

    let selected_route = router_res["selected_route"]
        .as_str()
        .unwrap_or("local_fast_llm");

    let final_answer = if selected_route == "cognitive_agent_swarm" {
        println!("🚀 ROUTER DIRECTS TO SWARM. Forwarding to Port 8002...");

        let swarm_res = state
            .http_client
            .post("http://127.0.0.1:8002/api/v1/swarm/execute")
            .json(&json!({ "user_id": req_body.user_id, "prompt": req_body.prompt }))
            .send()
            .await
            .unwrap()
            .json::<serde_json::Value>()
            .await
            .unwrap();

        swarm_res["final_output"]
            .as_str()
            .unwrap_or("Swarm processing failed.")
            .to_string()
    } else {
        println!("⚡ ROUTER DIRECTS TO LOCAL LLM. (Simulating fast local answer)...");
        format!("Simulated Fast LLM Answer for: {}", req_body.prompt)
    };

    state.semantic_cache.insert(
        req_body.prompt.clone(),
        (user_embedding, final_answer.clone()),
    );

    HttpResponse::Ok().json(GatewayResponse {
        status: "success".to_string(),
        source: format!("computed_by_{}", selected_route),
        message: final_answer,
        latency_ms: start_time.elapsed().as_millis(),
    })
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    println!("==================================================");
    println!("🚀 BOOTING PROJECT NEXUS: AetherOS Master Gateway");
    println!("==================================================");

    let openai_key = env::var("OPENAI_API_KEY")
        .expect("🚨 FATAL: OPENAI_API_KEY environment variable is required!");

    let app_state = web::Data::new(AppState {
        rate_limiter: DashMap::new(),
        semantic_cache: DashMap::new(),
        http_client: HttpClient::new(),
        openai_key,
    });

    HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .route("/api/v1/generate", web::post().to(process_prompt))
    })
    .bind(("127.0.0.1", 8080))?
    .run()
    .await
}
