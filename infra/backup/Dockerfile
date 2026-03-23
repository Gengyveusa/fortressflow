# Pinned: 2026-03-23
FROM alpine:3.19

RUN apk add --no-cache \
    postgresql16-client \
    aws-cli \
    bash \
    gzip \
    findutils

COPY backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh

RUN mkdir -p /backups

# Run backup daily at 2:00 AM via crond
RUN echo "0 2 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1" > /etc/crontabs/root

CMD ["crond", "-f", "-l", "2"]
