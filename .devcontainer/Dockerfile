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
    # Python (for PyCharm compatibility)
    python3 \
    python3-pip \
    # Networking tools
    iproute2 \
    # Project dependencies \
    libudev-dev libusb-1.0-0-dev libhidapi-libusb0 python3-dev python3-pil python3-pyudev libegl1 libgl1 \
    libopengl0 libxcb-cursor0 libxkbcommon0 mpg123 portaudio19-dev python3-pyaudio ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 (required for Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Create non-root user
RUN useradd -m -s /bin/bash -u 1001 developer && \
    echo "developer ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/developer && \
    chmod 0440 /etc/sudoers.d/developer

USER developer
WORKDIR /workspace


CMD ["/bin/bash"]