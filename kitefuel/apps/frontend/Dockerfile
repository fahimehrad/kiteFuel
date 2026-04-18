# ── KiteFuel frontend — production Dockerfile (multi-stage) ───────────────────
#
# Stage 1 (builder): install deps + run `vite build`
#   Build-time env vars are declared as ARGs so Vite can embed them:
#     VITE_API_BASE_URL       e.g. https://backend.railway.app
#     VITE_CONTRACT_ADDRESS   e.g. 0xAbc...
#
# Stage 2 (serve): copy the compiled dist/ into a minimal nginx image
#   Nginx serves the SPA on port 80 with SPA-friendly fallback routing.

# ── Stage 1: build ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies (layer-cached unless package-lock.json changes)
COPY package*.json ./
RUN npm ci --prefer-offline

# Declare build-time env vars (passed via --build-arg or Railway build vars)
ARG VITE_API_BASE_URL
ARG VITE_CONTRACT_ADDRESS

# Make them available to Vite at build time
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_CONTRACT_ADDRESS=$VITE_CONTRACT_ADDRESS

# Copy source and build
COPY . .
RUN npm run build

# ── Stage 2: serve ─────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS serve

# Remove default nginx static content
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# SPA routing: serve index.html for all unmatched paths (Vue Router history mode)
RUN printf 'server {\n\
    listen 80;\n\
    server_name _;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
\n\
    # SPA fallback — any path that is not a real file serves index.html\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
\n\
    # Cache hashed static assets aggressively\n\
    location ~* \\.(?:js|css|woff2?|png|svg|ico|webp)$ {\n\
        expires 1y;\n\
        add_header Cache-Control "public, immutable";\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
