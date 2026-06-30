# ==========================================
# STAGE 1: The Builder (The Factory)
# ==========================================
FROM rust:slim-bullseye AS builder

RUN apt-get update && apt-get install -y protobuf-compiler pkg-config libssl-dev

# Set the working directory to the ROOT of the virtual app
WORKDIR /app

# Copy BOTH the proto folder and the gateway folder into the container
COPY proto /app/proto
COPY aetheros_gateway /app/aetheros_gateway

# Move into the gateway folder to execute the build
WORKDIR /app/aetheros_gateway
RUN cargo build --release

# ==========================================
# STAGE 2: The Runner (The Vault)
# ==========================================
FROM debian:bullseye-slim
WORKDIR /app
RUN apt-get update && apt-get install -y ca-certificates libssl1.1 && rm -rf /var/lib/apt/lists/*

# Copy the final binary out of the nested target folder
COPY --from=builder /app/aetheros_gateway/target/release/aetheros_gateway .

EXPOSE 8080
CMD ["./aetheros_gateway"]