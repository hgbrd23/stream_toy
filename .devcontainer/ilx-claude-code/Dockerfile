
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    curl \
    wget \
    sudo \
    ca-certificates \
    gnupg \
    # Python (for PyCharm compatibility)
    python3 \
    python3-pip \
    # Docker CLI (for running tests via docker compose)
    docker.io \
    docker-compose-v2 \
    # Networking / debug tools
    iproute2 \
    iputils-ping \
    telnet \
    dnsutils \
    netcat-openbsd \
    traceroute \
    socat \
    jq \
    less \
    procps \
    # SSH
    openssh-server \
    openssh-client \
    # Session management tools
    tmux \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 (required for npx-launched MCP servers, e.g. chrome-devtools-mcp)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Configure SSH server
RUN mkdir -p /var/run/sshd && \
    # Configure SSH for public key authentication by default
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config && \
    sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#AuthorizedKeysFile/AuthorizedKeysFile/' /etc/ssh/sshd_config && \
    # Allow SSH login for ubuntu user
    echo 'AllowUsers ubuntu' >> /etc/ssh/sshd_config && \
    # Disable root login
    sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config

# Configure sudo for ubuntu user
RUN echo "ubuntu ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu && \
    chmod 0440 /etc/sudoers.d/ubuntu

# Add ubuntu user to docker group for socket access
RUN usermod -aG docker ubuntu

# Copy startup script
COPY prompt-agent.sh /scripts/prompt-agent.sh
RUN chmod +x /scripts/prompt-agent.sh

# Create workspace directory
RUN mkdir -p /workspace && chown ubuntu:ubuntu /workspace

# Expose SSH port (default 22, can be overridden with SSH_PORT env var)
EXPOSE 22

# Set default environment variables
ENV SSH_PORT=22
ENV SSH_PASSWORD_AUTH=false
ENV SETUP_CLAUDE_CODE=false
ENV USE_TMUX=false
ENV TMUX_LOG_TO_STDOUT=false
ENV CLAUDE_CONFIG_DIR=/workspace/.claude-profile

# Switch to ubuntu user for workspace
USER ubuntu
WORKDIR /workspace

CMD ["/bin/bash"]