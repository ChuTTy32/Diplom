FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# bpfcc-tools тянет python3-bpfcc — бинды BCC для Python 3
# linux-headers нужны bcc для JIT-компиляции BPF-программы под текущее ядро
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-bpfcc \
    bpfcc-tools \
    linux-headers-generic \
    libelf-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .

CMD ["python3", "agent.py"]
