# Stage 1: Build static assets with Node.js
FROM node:22-alpine AS builder

WORKDIR /app

# Install dependencies with lockfile consistency
COPY package.json package-lock.json ./
RUN npm ci

# Copy configuration and source files
COPY tsconfig.json vite.config.ts index.html app.html ./
COPY src/ ./src/
COPY public/ ./public/

# Configure API base URL to route through Nginx reverse proxy
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build production bundle into /app/dist
RUN npm run build

# Stage 2: Production web server with Nginx Alpine
FROM nginx:alpine

# Copy built assets to Nginx web root
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
