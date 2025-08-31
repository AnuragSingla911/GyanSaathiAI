# Single container GyanSaathiAI with all services
FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Core utilities
    curl wget gnupg2 software-properties-common supervisor nginx \
    # Node.js 20
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    # Python 3.11
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip \
    # PostgreSQL 16
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt/ jammy-pgdg main" > /etc/apt/sources.list.d/postgresql.list \
    && apt-get update \
    && apt-get install -y postgresql-16 postgresql-contrib-16 postgresql-16-pgvector \
    # MongoDB 7.0
    && curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/mongodb.gpg] http://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" > /etc/apt/sources.list.d/mongodb-org-7.0.list \
    && apt-get update \
    && apt-get install -y mongodb-org \
    # Redis
    && apt-get install -y redis-server \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create application directories
WORKDIR /app
RUN mkdir -p /app/backend /app/agent /app/frontend /app/ops \
    && mkdir -p /var/lib/postgresql/data /var/lib/mongodb \
    && mkdir -p /var/log/supervisor /var/log/nginx \
    && chown -R postgres:postgres /var/lib/postgresql \
    && chown -R mongodb:mongodb /var/lib/mongodb

# Copy source code
COPY backend/ /app/backend/
COPY agent/ /app/agent/
COPY frontend/ /app/frontend/
COPY ops/ /app/ops/

# Install backend dependencies
WORKDIR /app/backend
RUN npm install

# Install agent dependencies
WORKDIR /app/agent
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt --break-system-packages

# Build frontend
WORKDIR /app/frontend
RUN npm install && npm run build

# Copy built frontend to nginx
RUN cp -r /app/frontend/dist/* /usr/share/nginx/html/

# Copy configuration files
COPY ops/nginx/nginx.conf /etc/nginx/nginx.conf
COPY ops/supervisor/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY ops/scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Configure PostgreSQL
USER postgres
RUN /usr/lib/postgresql/16/bin/initdb -D /var/lib/postgresql/data \
    && echo "host all all 127.0.0.1/32 trust" >> /var/lib/postgresql/data/pg_hba.conf \
    && echo "listen_addresses = '127.0.0.1'" >> /var/lib/postgresql/data/postgresql.conf

USER root

# Configure Redis
RUN sed -i 's/bind 127.0.0.1 ::1/bind 127.0.0.1/' /etc/redis/redis.conf \
    && sed -i 's/daemonize yes/daemonize no/' /etc/redis/redis.conf

# Configure MongoDB
RUN echo "bind_ip = 127.0.0.1" >> /etc/mongod.conf

# Environment variables
ENV NODE_ENV=production
ENV PORT=5000
ENV POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/aitutor
ENV MONGO_URL=mongodb://localhost:27017/aitutor
ENV REDIS_URL=redis://localhost:6379/0
ENV AGENT_POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/aitutor
ENV AGENT_MONGO_URL=mongodb://localhost:27017/aitutor

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost/api/v1/health || exit 1

# Expose only HTTP port
EXPOSE 80

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
