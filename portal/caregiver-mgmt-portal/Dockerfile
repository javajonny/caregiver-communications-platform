# Stage 1: Build
FROM node:20-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Ensure we build for production
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine
# Copy the built assets from the builder stage
COPY --from=builder /app/dist /usr/share/nginx/html
# Copy our custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# We rely on volume mounts for certs in docker-compose, 
# but we expose 443 to indicate this container listens on HTTPS
EXPOSE 443

CMD ["nginx", "-g", "daemon off;"]
