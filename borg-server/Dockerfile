FROM debian:bookworm-slim

# borg — хранилище; openssh-server — транспорт borg serve; wireguard — туннель
RUN apt-get update && apt-get install -y --no-install-recommends \
    borgbackup openssh-server wireguard-tools iproute2 iptables procps \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 51820/udp

ENTRYPOINT ["/entrypoint.sh"]
