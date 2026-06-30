# ==========================================
# STAGE 1: Dependencies
# ==========================================
FROM node:20-alpine AS deps
WORKDIR /app
# Copy only the package files to utilize Docker cache
COPY nexus-dashboard/package.json nexus-dashboard/package-lock.json ./
RUN npm ci

# ==========================================
# STAGE 2: The Builder (The Factory)
# ==========================================
FROM node:20-alpine AS builder
WORKDIR /app

# Copy the monorepo context
COPY nexus-dashboard /app/nexus-dashboard
COPY proto /app/proto

WORKDIR /app/nexus-dashboard
# Bring in the installed dependencies from Stage 1
COPY --from=deps /app/node_modules ./node_modules

# Compile the React code into optimized static HTML/CSS/JS
RUN npm run build

# ==========================================
# STAGE 3: The Runner (The Vault)
# ==========================================
FROM node:20-alpine AS runner
WORKDIR /app

# Set the environment to Production using modern syntax
ENV NODE_ENV=production

# THE MAGIC: Copy ONLY the standalone server, the static assets, and the public folder.
COPY --from=builder /app/nexus-dashboard/public ./public
COPY --from=builder /app/nexus-dashboard/.next/standalone ./
COPY --from=builder /app/nexus-dashboard/.next/static ./.next/static

# Set the port using modern syntax
EXPOSE 3000
ENV PORT=3000

# Execute the standalone Node server
CMD ["node", "server.js"]