# Stage 1: Build React app (with auto-generated schema manifest)
FROM node:20-alpine AS build

# Install Python for schema generation
RUN apk add --no-cache python3

WORKDIR /repo

# Copy schema source files for manifest generation
COPY scripts/generate-schema-manifest.py ./scripts/
COPY services/tracker/app/schema.py ./services/tracker/app/
COPY services/tracker/app/routers/lookups.py ./services/tracker/app/routers/
COPY services/pipeline/schema.py ./services/pipeline/
COPY services/comments/app/core/schema.py ./services/comments/app/core/
COPY services/work/schema.py ./services/work/

# Install frontend dependencies
WORKDIR /repo/frontend
COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps

# Copy frontend source
COPY frontend/ .

# Generate schema manifest AFTER frontend copy (overwrites any stale version)
RUN mkdir -p src/data && python3 /repo/scripts/generate-schema-manifest.py

ARG REACT_APP_API_URL=
ENV REACT_APP_API_URL=$REACT_APP_API_URL

RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

COPY --from=build /repo/frontend/build /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/.htpasswd /etc/nginx/.htpasswd

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
