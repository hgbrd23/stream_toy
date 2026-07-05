#!/bin/bash
set -e

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting container initialization..."

# Setup SSH keys from environment variables
if [ -n "$SSH_PUBLIC_KEY" ]; then
    log "Setting up SSH public key from environment variable"
    mkdir -p /home/ubuntu/.ssh
    echo "$SSH_PUBLIC_KEY" > /home/ubuntu/.ssh/authorized_keys
    chmod 700 /home/ubuntu/.ssh
    chmod 600 /home/ubuntu/.ssh/authorized_keys
    chown -R ubuntu:ubuntu /home/ubuntu/.ssh
    log "SSH public key configured successfully"
else
    log "No SSH_PUBLIC_KEY environment variable found - SSH key authentication not configured"
fi

# Setup additional SSH keys if provided (comma-separated)
if [ -n "$SSH_ADDITIONAL_KEYS" ]; then
    log "Adding additional SSH public keys"
    IFS=',' read -ra KEYS <<< "$SSH_ADDITIONAL_KEYS"
    for key in "${KEYS[@]}"; do
        echo "$key" >> /home/ubuntu/.ssh/authorized_keys
    done
    log "Added ${#KEYS[@]} additional SSH keys"
fi

# Ensure SSH directory has correct permissions
if [ -d "/home/ubuntu/.ssh" ]; then
    chmod 700 /home/ubuntu/.ssh
    chmod 600 /home/ubuntu/.ssh/authorized_keys 2>/dev/null || true
    chown -R ubuntu:ubuntu /home/ubuntu/.ssh
fi

# Generate host keys if they don't exist
if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
    log "Generating SSH host keys"
    sudo ssh-keygen -A
fi

# Configure SSH based on environment variables
if [ -n "$SSH_PORT" ]; then
    log "Setting SSH port to $SSH_PORT"
    sudo sed -i "s/^#Port 22/Port $SSH_PORT/" /etc/ssh/sshd_config
    sudo sed -i "s/^Port 22/Port $SSH_PORT/" /etc/ssh/sshd_config
fi

if [ "$SSH_PASSWORD_AUTH" = "true" ]; then
    log "Enabling SSH password authentication"
    sudo sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
fi

# Setup tmux logging directory
sudo mkdir -p /var/log/tmux
sudo chown ubuntu:ubuntu /var/log/tmux

# Setup tmux auto-reconnect
if [ "$USE_TMUX" = "true" ]; then
    log "Setting up tmux auto-reconnect with logging"

    # Create tmux configuration with logging enabled
    cat > /home/ubuntu/.tmux.conf << 'EOF'
# Enable logging
set -g history-limit 50000

# Log all pane output to files
set-hook -g after-new-session 'run-shell "tmux pipe-pane -t #{session_name}:#{window_index}.#{pane_index} -o \"cat >> /var/log/tmux/session-#{session_name}-#{window_index}-#{pane_index}.log\""'
set-hook -g after-new-window 'run-shell "tmux pipe-pane -t #{session_name}:#{window_index}.#{pane_index} -o \"cat >> /var/log/tmux/session-#{session_name}-#{window_index}-#{pane_index}.log\""'
set-hook -g after-split-window 'run-shell "tmux pipe-pane -t #{session_name}:#{window_index}.#{pane_index} -o \"cat >> /var/log/tmux/session-#{session_name}-#{window_index}-#{pane_index}.log\""'

# Optional: Add timestamps to logs
# set-hook -g after-new-session 'run-shell "tmux pipe-pane -t #{session_name}:#{window_index}.#{pane_index} -o \"while IFS= read -r line; do echo \\\"\$(date +\\'%Y-%m-%d %H:%M:%S\\') \$line\\\"; done >> /var/log/tmux/session-#{session_name}-#{window_index}-#{pane_index}.log\""'
EOF
    chown ubuntu:ubuntu /home/ubuntu/.tmux.conf

    # Create the claude-session function in a separate file
    cat > /home/ubuntu/.claude-session.sh << 'EOF'
#!/bin/bash
# Claude session management function
claude-session() {
  local marker="$CLAUDE_CONFIG_DIR/.claude-session-started"
  if [[ -f "$marker" ]]; then
    claude --resume
  else
    touch "$marker"
    claude "$(cat /scripts/prompt.txt)"
  fi
}
EOF
    chmod +x /home/ubuntu/.claude-session.sh
    chown ubuntu:ubuntu /home/ubuntu/.claude-session.sh

    # Source it from .bashrc for interactive shells
    cat >> /home/ubuntu/.bashrc << 'EOF'

# Source Claude session function
if [ -f ~/.claude-session.sh ]; then
    source ~/.claude-session.sh
fi
EOF

    # Create a script that automatically attaches to or creates tmux session
    cat > /home/ubuntu/.tmux_attach.sh << 'EOF'
#!/bin/bash
# Auto-attach to tmux session or create new one
if tmux has-session -t main 2>/dev/null; then
    exec tmux attach-session -t main
else
    # Create new session and run claude-session if SETUP_CLAUDE_CODE is true
    if [[ "$SETUP_CLAUDE_CODE" == "true" ]]; then
        exec tmux new-session -s main -c /workspace "bash -c 'source ~/.claude-session.sh; claude-session; exec bash'"
    else
        exec tmux new-session -s main -c /workspace
    fi
fi
EOF
    chmod +x /home/ubuntu/.tmux_attach.sh
    chown ubuntu:ubuntu /home/ubuntu/.tmux_attach.sh

    # Modify ubuntu's shell to automatically start tmux on SSH login
    echo '' >> /home/ubuntu/.bashrc
    echo '# Auto-attach to tmux session on SSH login' >> /home/ubuntu/.bashrc
    echo 'if [[ -z "$TMUX" && -n "$SSH_CONNECTION" ]]; then' >> /home/ubuntu/.bashrc
    echo '    exec /home/ubuntu/.tmux_attach.sh' >> /home/ubuntu/.bashrc
    echo 'fi' >> /home/ubuntu/.bashrc

    chown ubuntu:ubuntu /home/ubuntu/.bashrc
fi

# Start SSH service
log "Starting SSH service"
sudo /usr/sbin/sshd

# Check if SSH is running
if pgrep sshd > /dev/null; then
    log "SSH service started successfully"
else
    log "ERROR: Failed to start SSH service"
    exit 1
fi

# Setup Claude Code session if requested
if [ "$SETUP_CLAUDE_CODE" = "true" ]; then
    log "Setting up Claude Code session environment"

    # Check if claude is already installed
    if ! command -v claude &> /dev/null; then
        log "Installing Claude Code CLI globally"
        sudo npm install -g @anthropic-ai/claude-code
        log "Claude Code CLI installed successfully"
    else
        log "Claude Code CLI already installed"
    fi
fi

# Start initial tmux session if requested
if [ "$USE_TMUX" = "true" ]; then
    log "Starting initial tmux session with logging"
    if [ "$SETUP_CLAUDE_CODE" = "true" ]; then
        log "Starting tmux session with claude-session"
        cd /workspace && tmux new-session -d -s main 'bash -c "source ~/.claude-session.sh; claude-session; exec bash"'
    else
        cd /workspace && tmux new-session -d -s main
    fi

    # Wait a moment for tmux session to start
    sleep 2

    # Enable logging for the main session
    log "Enabling tmux logging for session 'main'"
    tmux pipe-pane -t main:0.0 -o 'cat >> /var/log/tmux/session-main-0-0.log'
fi

log "Container initialization completed"

# Start log monitoring in background if requested
if [ "$TMUX_LOG_TO_STDOUT" = "true" ] && [ "$USE_TMUX" = "true" ]; then
    log "Starting tmux log monitoring to container stdout"
    (
        # Wait for log file to be created
        while [ ! -f /var/log/tmux/session-main-0-0.log ]; do
            sleep 1
        done

        # Tail the tmux log to container stdout
        tail -f /var/log/tmux/session-main-0-0.log 2>/dev/null | while IFS= read -r line; do
            echo "[TMUX] $line"
        done
    ) &
fi

# Execute the main command or keep container running
if [ $# -eq 0 ]; then
    log "No command specified, keeping container running"
    if [ "$TMUX_LOG_TO_STDOUT" = "true" ] && [ "$USE_TMUX" = "true" ]; then
        # Keep container running but also show logs
        tail -f /dev/null
    else
        tail -f /dev/null
    fi
else
    log "Executing command: $@"
    exec "$@"
fi
