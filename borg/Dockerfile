FROM debian:bookworm-slim

# openssh-client — borg по ssh:// до borg-server; wireguard — туннель до него
RUN apt-get update && apt-get install -y --no-install-recommends \
    borgbackup python3 python3-pip curl \
    openssh-client wireguard-tools iproute2 iptables procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
