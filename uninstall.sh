#!/bin/bash
#
# StreamToy Uninstall Script
#
# This script removes StreamToy from the system
#
# Usage: sudo ./uninstall.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/stream_toy"
SERVICE_NAME="stream_toy"
UDEV_RULES="/etc/udev/rules.d/99-streamdock.rules"

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

# Function to ask yes/no question
ask_yes_no() {
    local prompt="$1"
    local response

    while true; do
        read -p "$prompt [y/N]: " response
        case "$response" in
            [Yy]* ) return 0;;
            [Nn]* | "" ) return 1;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

# Main uninstall function
main() {
    echo ""
    echo "============================================"
    echo "  StreamToy Uninstall Script"
    echo "============================================"
    echo ""

    check_root

    log_warning "This will remove StreamToy from your system."
    echo ""

    if ! ask_yes_no "Are you sure you want to continue?"; then
        log_info "Uninstall cancelled"
        exit 0
    fi

    echo ""
    log_info "Starting uninstall process..."
    echo ""

    # Stop and disable service
    log_info "Stopping and disabling service..."
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        systemctl stop "$SERVICE_NAME"
        log_success "Service stopped"
    fi

    if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
        systemctl disable "$SERVICE_NAME"
        log_success "Service disabled"
    fi

    # Remove service file
    if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
        log_info "Removing service file..."
        rm "/etc/systemd/system/${SERVICE_NAME}.service"
        systemctl daemon-reload
        log_success "Service file removed"
    fi

    # Remove application directory
    if [ -d "$INSTALL_DIR" ]; then
        log_info "Removing application directory..."
        rm -rf "$INSTALL_DIR"
        log_success "Application removed"
    fi

    # Remove udev rules
    if [ -f "$UDEV_RULES" ]; then
        if ask_yes_no "Remove udev rules for StreamDock?"; then
            log_info "Removing udev rules..."
            rm "$UDEV_RULES"
            udevadm control --reload-rules
            udevadm trigger
            log_success "Udev rules removed"
        else
            log_info "Keeping udev rules"
        fi
    fi

    echo ""

    # Ask about configuration files
    echo ""
    log_warning "Configuration files can be restored from backups:"
    echo "  - /boot/firmware/config.txt.backup"
    echo "  - /etc/asound.conf.backup"
    echo ""

    if ask_yes_no "Do you want to restore configuration file backups?"; then
        if [ -f "/boot/firmware/config.txt.backup" ]; then
            log_info "Restoring boot config..."
            cp "/boot/firmware/config.txt.backup" "/boot/firmware/config.txt"
            log_success "Boot config restored"
            log_warning "Reboot required to apply boot config changes"
        fi

        if [ -f "/etc/asound.conf.backup" ]; then
            log_info "Restoring ALSA config..."
            cp "/etc/asound.conf.backup" "/etc/asound.conf"
            log_success "ALSA config restored"
        fi
    else
        log_info "Configuration files not restored"
        log_info "You can manually restore them later if needed"
    fi

    # Uninstall complete
    echo ""
    echo "============================================"
    log_success "Uninstall complete!"
    echo "============================================"
    echo ""

    if [ -f "/boot/firmware/config.txt.backup" ]; then
        log_info "Note: System packages were NOT removed."
        log_info "If you want to remove packages, use:"
        echo "  ${YELLOW}sudo apt remove --autoremove python3-venv python3-pip ffmpeg${NC}"
    fi

    echo ""
}

# Run main function
main "$@"
