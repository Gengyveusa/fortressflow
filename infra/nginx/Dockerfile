# Pinned: 2026-03-23
FROM nginx:alpine@sha256:08fe94b0d1e72fc687840f5696f6e107a85c327b1bcb8a7acc22f8c100227c67

# Remove default nginx config and replace with ours
RUN rm /etc/nginx/nginx.conf

COPY nginx.conf /etc/nginx/nginx.conf

# Create log directory (already exists in base image, but ensure permissions)
RUN mkdir -p /var/log/nginx \
    && chown -R nginx:nginx /var/log/nginx

EXPOSE 80

# Healthcheck: wget is available in nginx:alpine; check /health which proxies to backend
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
