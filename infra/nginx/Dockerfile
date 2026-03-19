FROM nginx:alpine

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
