# ==============================================================================
# Autonomous AI Job Application Agent - Frontend Dockerfile
# Production Multi-Stage Build (Node.js 20 Alpine + Nginx 1.27 Alpine)
# ==============================================================================

# Stage 1: Build the Vite React Single-Page Application
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency manifests first for layer caching
COPY package.json package-lock.json ./
RUN npm ci

# Copy frontend source files
COPY . ./

# Build optimized production assets (outputs to /app/dist)
RUN npm run build

# Stage 2: Serve compiled assets with high-performance Nginx reverse proxy
FROM nginx:1.27-alpine AS production

# Install curl for container orchestration health checks
RUN apk add --no-cache curl

# Copy custom enterprise Nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy production bundle from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Set non-root web directory permissions
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

# Expose HTTP port
EXPOSE 80

# Automated Docker Healthcheck against Nginx /healthz
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/healthz || exit 1

# Start Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
