#!/bin/bash
#
# StreamToy Installation Script
#
# This script installs StreamToy to /opt/stream_toy and configures it to run at system startup.
# It performs the following tasks:
# - Checks and configures Raspberry Pi settings (config.txt, ALSA)
# - Installs required system packages
# - Creates virtual environment and installs Python dependencies
# - Creates systemd service for autostart
#
# Usage: sudo ./install.sh [--keep-venv]
#
# Options:
#   --keep-venv    Keep existing virtual environment (skip venv deletion)

set -e  # Exit on any error

# Parse command line arguments
KEEP_VENV=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-venv)
            KEEP_VENV=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: sudo ./install.sh [--keep-venv]"
            exit 1
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/stream_toy"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${INSTALL_DIR}/.venv"
SERVICE_NAME="stream_toy"
BOOT_CONFIG="/boot/firmware/config.txt"
BOOT_CONFIG_OLD="/boot/config.txt"
ASOUND_CONF="/etc/asound.conf"

# Function to print colored messages
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Function to determine boot config location
find_boot_config() {
    if [ -f "$BOOT_CONFIG" ]; then
        echo "$BOOT_CONFIG"
    elif [ -f "$BOOT_CONFIG_OLD" ]; then
        echo "$BOOT_CONFIG_OLD"
    else
        log_error "Boot config not found at $BOOT_CONFIG or $BOOT_CONFIG_OLD"
        exit 1
    fi
}

# Function to check if a line exists in a file
line_exists() {
    local file="$1"
    local pattern="$2"
    grep -q "^${pattern}" "$file" 2>/dev/null
}

# Function to check if a line exists (including commented)
line_exists_anywhere() {
    local file="$1"
    local pattern="$2"
    grep -q "${pattern}" "$file" 2>/dev/null
}

# Function to add or update config line
add_or_update_config() {
    local file="$1"
    local line="$2"
    local pattern="$3"

    if line_exists "$file" "$pattern"; then
        log_success "Config already present: $pattern"
    elif line_exists_anywhere "$file" "$pattern"; then
        log_warning "Config exists but is commented, uncommenting: $pattern"
        sed -i "s/^#*${pattern}.*/${line}/" "$file"
    else
        log_info "Adding config: $line"
        echo "$line" >> "$file"
    fi
}

# Function to comment out a line
comment_out_line() {
    local file="$1"
    local pattern="$2"

    if line_exists "$file" "$pattern"; then
        log_info "Commenting out: $pattern"
        sed -i "s/^${pattern}/#${pattern}/" "$file"
    fi
}

# Check Raspberry Pi boot configuration
configure_boot_config() {
    log_info "Configuring Raspberry Pi boot settings..."

    local boot_config=$(find_boot_config)
    log_info "Using boot config: $boot_config"

    # Backup original config
    if [ ! -f "${boot_config}.backup" ]; then
        log_info "Creating backup: ${boot_config}.backup"
        cp "$boot_config" "${boot_config}.backup"
    fi

    # Check and add I2S audio support
    add_or_update_config "$boot_config" "dtparam=i2s=on" "dtparam=i2s"

    # Check and add SPI support
    add_or_update_config "$boot_config" "dtparam=spi=on" "dtparam=spi"

    # Check and add UART support
    add_or_update_config "$boot_config" "enable_uart=1" "enable_uart"

    # Disable built-in analog audio (comment it out)
    comment_out_line "$boot_config" "dtparam=audio=on"

    # Check for [all] section and add overlays there
    if ! grep -q "^\[all\]" "$boot_config"; then
        log_info "Adding [all] section to boot config"
        echo "" >> "$boot_config"
        echo "[all]" >> "$boot_config"
    fi

    # Add MAX98357A overlay after [all] section
    if ! grep -A 20 "^\[all\]" "$boot_config" | grep -q "dtoverlay=max98357a"; then
        log_info "Adding MAX98357A audio overlay"
        sed -i '/^\[all\]/a dtoverlay=max98357a,sdmode-pin=23' "$boot_config"
    else
        log_success "MAX98357A overlay already configured"
    fi

    # Add GPIO activity LED after [all] section
    if ! grep -A 20 "^\[all\]" "$boot_config" | grep -q "dtparam=act_led_gpio"; then
        log_info "Adding GPIO activity LED configuration"
        sed -i '/^\[all\]/a dtparam=act_led_trigger=heartbeat' "$boot_config"
        sed -i '/^\[all\]/a dtparam=act_led_gpio=26' "$boot_config"
    else
        log_success "GPIO activity LED already configured"
    fi

    log_success "Boot configuration complete"
}

# Configure ALSA sound
configure_alsa() {
    log_info "Configuring ALSA sound system..."

    # Backup existing config if it exists
    if [ -f "$ASOUND_CONF" ] && [ ! -f "${ASOUND_CONF}.backup" ]; then
        log_info "Creating backup: ${ASOUND_CONF}.backup"
        cp "$ASOUND_CONF" "${ASOUND_CONF}.backup"
    fi

    # Always regenerate ALSA configuration
    log_info "Writing ALSA configuration to $ASOUND_CONF"
    cat > "$ASOUND_CONF" <<'EOF'
# Default device uses plug for automatic conversion with software volume control
pcm.!default {
  type plug
  slave.pcm "softvol_dmixer"
}

# Software volume control (MAX98357A has no hardware volume)
pcm.softvol_dmixer {
  type softvol
  slave.pcm "dmixer"
  control {
    name "SoftMaster"
    card 0
  }
  min_dB -51.0
  max_dB 0.0
}

# Dmix configuration with larger buffers for Raspberry Pi Zero 2 W
# Prevents buffer underruns and audio stuttering
pcm.dmixer {
  type dmix
  ipc_key 1024
  ipc_key_add_uid yes
  ipc_perm 0666
  slave {
      pcm "hw:0,0"
      rate 48000
      period_size 2048     # 42.7ms periods (was 1024/21.3ms)
      buffer_size 16384    # 341ms total buffer (was 4096/85ms)
  }
}

# Control device
ctl.!default {
  type hw
  card 0
}
EOF
    log_success "ALSA configuration written"
}

# Install system packages
install_system_packages() {
    log_info "Installing system packages..."

    # Update package list
    log_info "Updating package list..."
    apt-get update -qq

    # Install required packages
    log_info "Installing dependencies (this may take a few minutes)..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        libudev-dev \
        libusb-1.0-0-dev \
        libhidapi-libusb0 \
        python3-dev \
        python3-pil \
        python3-pyudev \
        python3-venv \
        python3-pip \
        libegl1 \
        libgl1 \
        libopengl0 \
        libxcb-cursor0 \
        libxkbcommon0 \
        mpg123 \
        portaudio19-dev \
        python3-pyaudio \
        libasound2-dev \
        ffmpeg \
        git \
        > /dev/null 2>&1

    log_success "System packages installed"
}

# Create installation directory and copy files
install_application() {
    log_info "Installing StreamToy application to $INSTALL_DIR..."

    # Create install directory
    if [ ! -d "$INSTALL_DIR" ]; then
        log_info "Creating directory: $INSTALL_DIR"
        mkdir -p "$INSTALL_DIR"
    fi

    # Copy application files
    log_info "Copying application files..."
    rsync -a --delete \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='.venv' \
        --exclude='.venv-emulator' \
        --exclude='data' \
        --exclude='*.log' \
        "$SCRIPT_DIR/" "$INSTALL_DIR/"

    # Create data directory with proper permissions
    log_info "Creating data directory..."
    mkdir -p "${INSTALL_DIR}/data"
    chmod 755 "${INSTALL_DIR}/data"

    log_success "Application files installed"
}

# Setup Python virtual environment
setup_venv() {
    log_info "Setting up Python virtual environment..."

    # Check if we should keep existing venv
    if [ "$KEEP_VENV" = true ] && [ -d "$VENV_DIR" ]; then
        log_info "Keeping existing virtual environment (--keep-venv specified)"
    else
        # Remove old venv if exists
        if [ -d "$VENV_DIR" ]; then
            log_warning "Removing old virtual environment"
            rm -rf "$VENV_DIR"
        fi

        # Create virtual environment
        log_info "Creating virtual environment at $VENV_DIR"
        python3 -m venv "$VENV_DIR"
    fi

    # Activate venv and upgrade pip
    log_info "Upgrading pip..."
    "$VENV_DIR/bin/pip" install --upgrade pip wheel > /dev/null 2>&1

    # Install requirements
    log_info "Installing Python dependencies (this may take several minutes)..."
    "$VENV_DIR/bin/pip" install -r "${INSTALL_DIR}/requirements.txt" > /dev/null 2>&1

    log_success "Python environment configured"
}

# Configure udev rules for StreamDock access
configure_udev() {
    log_info "Configuring udev rules for StreamDock device..."

    local udev_rules="/etc/udev/rules.d/99-streamdock.rules"

    if [ -f "$udev_rules" ]; then
        log_success "Udev rules already exist"
    else
        log_info "Creating udev rules"
        cat > "$udev_rules" <<'EOF'
# StreamDock USB HID device access
# MiraBox HSV 293V3 / StreamDock 293V3
SUBSYSTEM=="usb", ATTRS{idVendor}=="0c45", ATTRS{idProduct}=="7403", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0c45", ATTRS{idProduct}=="7403", MODE="0666", GROUP="plugdev"
EOF

        # Reload udev rules
        udevadm control --reload-rules
        udevadm trigger

        log_success "Udev rules configured"
    fi
}

# Create systemd service
create_systemd_service() {
    log_info "Creating systemd service..."

    local service_file="/etc/systemd/system/${SERVICE_NAME}.service"

    cat > "$service_file" <<EOF
[Unit]
Description=StreamToy Interactive Game Framework
After=network.target sound.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
Environment="PYTHONPATH=${INSTALL_DIR}/StreamDock-Device-SDK/Python-Linux-SDK/src"
ExecStart=${VENV_DIR}/bin/python3 ${INSTALL_DIR}/main.py --log-level INFO
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

# Resource limits
MemoryLimit=512M
CPUQuota=80%

[Install]
WantedBy=multi-user.target
EOF

    log_success "Systemd service created: $service_file"

    # Reload systemd
    log_info "Reloading systemd daemon..."
    systemctl daemon-reload

    # Enable service
    log_info "Enabling service to start at boot..."
    systemctl enable "$SERVICE_NAME"

    log_success "Service enabled"
}

# Main installation function
main() {
    echo ""
    echo "============================================"
    echo "  StreamToy Installation Script"
    echo "============================================"
    echo ""

    check_root

    log_info "Starting installation process..."
    echo ""

    # Step 1: System configuration
    log_info "Step 1: Configuring Raspberry Pi system..."
    configure_boot_config
    configure_alsa
    echo ""

    # Step 2: Install packages
    log_info "Step 2: Installing system packages..."
    install_system_packages
    echo ""

    # Step 3: Install application
    log_info "Step 3: Installing StreamToy application..."
    install_application
    echo ""

    # Step 4: Setup Python environment
    log_info "Step 4: Setting up Python environment..."
    setup_venv
    echo ""

    # Step 5: Configure udev rules
    log_info "Step 5: Configuring device access..."
    configure_udev
    echo ""

    # Step 6: Create service
    log_info "Step 6: Creating system service..."
    create_systemd_service
    echo ""

    # Installation complete
    echo ""
    echo -e "╔════════════════════════════════════════════════════════════╗"
    echo -e "║                                                            ║"
    echo -e "║            ${GREEN}✓ StreamToy Installation Complete!${NC}             ║"
    echo -e "║                                                            ║"
    echo -e "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo -e "${GREEN}┌─ Installation Summary ─────────────────────────────────┐${NC}"
    echo -e "${GREEN}│${NC} ✓ System configuration applied                         ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC} ✓ All dependencies installed                           ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC} ✓ Application deployed to ${INSTALL_DIR}          ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC} ✓ Python environment configured                        ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC} ✓ Device permissions configured                        ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC} ✓ Systemd service created and enabled                  ${GREEN}│${NC}"
    echo -e "${GREEN}└────────────────────────────────────────────────────────┘${NC}"
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  ${YELLOW}IMPORTANT: Reboot Required${NC}                               ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  System configuration changes require a reboot to take effect."
    echo "  StreamToy will start automatically after reboot."
    echo ""
    echo -e "  ${GREEN}→${NC} Reboot now:"
    echo -e "    ${YELLOW}sudo reboot${NC}"
    echo ""
    echo -e "${BLUE}────────────────────────────────────────────────────────────${NC}"
    echo ""
    echo -e "${BLUE}After Reboot:${NC}"
    echo ""
    echo -e "  ${GREEN}→${NC} Check service status:"
    echo -e "    ${YELLOW}sudo systemctl status stream_toy${NC}"
    echo ""
    echo -e "  ${GREEN}→${NC} View live logs:"
    echo -e "    ${YELLOW}sudo journalctl -u stream_toy -f${NC}"
    echo ""
    echo -e "  ${GREEN}→${NC} Control the service:"
    echo -e "    ${YELLOW}sudo systemctl start stream_toy${NC}    # Start"
    echo -e "    ${YELLOW}sudo systemctl stop stream_toy${NC}     # Stop"
    echo -e "    ${YELLOW}sudo systemctl restart stream_toy${NC}  # Restart"
    echo ""
    echo -e "${BLUE}────────────────────────────────────────────────────────────${NC}"
    echo ""
    echo -e "${BLUE}Quick Reference:${NC}"
    echo -e "  ${GREEN}→${NC} Exit the app: Long-press bottom-right button (⚙)"
    echo -e "  ${GREEN}→${NC} Install location: ${INSTALL_DIR}"
    echo -e "  ${GREEN}→${NC} Virtual environment: ${VENV_DIR}"
    echo -e "  ${GREEN}→${NC} Service file: /etc/systemd/system/${SERVICE_NAME}.service"
    echo -e "  ${GREEN}→${NC} Documentation: See INSTALL.md and QUICKSTART.md"
    echo ""
    echo -e "${GREEN}────────────────────────────────────────────────────────────${NC}"
    echo ""
    echo -e "  ${GREEN}✓${NC} Installation successful! Enjoy StreamToy!"
    echo ""
}

# Run main function
main "$@"
