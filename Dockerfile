FROM kalilinux/kali-rolling:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        adb \
        metasploit-framework \
        nmap \
        scrcpy \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN python3 -m pip install --break-system-packages --no-cache-dir .

ENTRYPOINT ["android-crack"]
CMD ["--help"]
