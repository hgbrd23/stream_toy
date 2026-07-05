# ilx-claude-docker: Claude Code Container with SSH Access

This stack provides a Docker-based Ubuntu 24.04 container that is accessible over SSH and automatically starts a Claude Code session with a preset prompt (`prompt.txt`). 
Connect via SSH, and Claude is already running in a tmux session.

The same Dockerfile is also reused by the parent folder's `devcontainer.json` for IDE-based development -- see [../ README](../README.md) for details.

## How It Works

When started with `docker compose up`, the container:

1. Runs `prompt-agent.sh` as its entrypoint, which:
   - Configures SSH public key authentication for the `ubuntu` user
   - Starts an OpenSSH server on port 22 (mapped to 2222 on the host)
   - Installs Claude Code CLI globally via npm (if `SETUP_CLAUDE_CODE=true`)
   - Creates a tmux session named `main` that auto-launches `claude` with the contents of `prompt.txt` as the initial prompt
   - Pipes tmux output to `/var/log/tmux/` and optionally to container stdout
2. On SSH login, the user is automatically attached to the running tmux session, landing directly in the Claude Code conversation.
3. On reconnect, Claude Code resumes the previous session (`claude --resume`) instead of starting fresh.

## Quick Start

1. **Set your SSH public key** in `docker-compose.yml`:
   ```yaml
   - SSH_PUBLIC_KEY=ssh-rsa AAAA... your-key-here
   ```

2. **Build and start:**
   ```bash
   cd .devcontainer/ilx-claude-docker
   docker compose build
   docker compose up -d
   ```

3. **Connect:**
   ```bash
   ssh -p 2222 ubuntu@localhost
   ```
   You will land in a tmux session with Claude Code already running.

4. **Customize the prompt** by editing `prompt.txt`. This is the initial message sent to Claude on first session start. Restart the container to pick up changes.

## Configuration

### Environment Variables (docker-compose.yml)

| Variable | Default | Description |
|-|-|-|
| `SSH_PUBLIC_KEY` | *(required)* | SSH public key for the `ubuntu` user |
| `SSH_ADDITIONAL_KEYS` | - | Comma-separated additional SSH public keys |
| `SSH_PORT` | 22 | SSH port inside container (host-mapped separately) |
| `SSH_PASSWORD_AUTH` | false | Enable password auth (not recommended) |
| `SETUP_CLAUDE_CODE` | true | Install Claude Code CLI and enable auto-session |
| `USE_TMUX` | true | Enable tmux session management and auto-attach on SSH |
| `TMUX_LOG_TO_STDOUT` | true | Forward tmux session logs to `docker compose logs` |
| `CLAUDE_CONFIG_DIR` | /workspace/.claude-profile | Claude Code config/state directory |

### Volumes

| Mount | Purpose |
|-|-|
| `./workspace:/workspace` | Persistent workspace (code, config, Claude profile) |
| `./prompt.txt:/scripts/prompt.txt:ro` | Initial Claude Code prompt (read-only) |
| `/var/run/docker.sock:/var/run/docker.sock` | Docker-in-Docker access (for running tests, Odoo stack, etc.) |

## File Structure

```
ilx-claude-docker/
  Dockerfile           Ubuntu 24.04 image with Python, Node.js, Docker CLI, SSH
  docker-compose.yml   Standalone stack config (SSH + Claude + tmux)
  prompt-agent.sh      Container entrypoint: SSH setup, Claude install, tmux session
  prompt.txt           Initial prompt sent to Claude Code on first session start
```

## Session Lifecycle

### First SSH connection
- tmux session `main` is created during container startup
- Claude Code starts with the prompt from `prompt.txt`
- A marker file (`$CLAUDE_CONFIG_DIR/.claude-session-started`) is written

### Subsequent SSH connections
- You are reattached to the existing tmux session
- If Claude Code is invoked again via `claude-session`, it runs `claude --resume` to continue the previous conversation

### Container restart
- The tmux session is recreated
- If the marker file persists (workspace is a volume), Claude resumes; otherwise a fresh session starts with the prompt

## Included Software

- **Ubuntu 24.04** base
- **Python 3** + pip
- **Node.js 20** (required by Claude Code)
- **Docker CLI** + docker-compose-v2 (Docker-in-Docker via socket mount)
- **OpenSSH server** (public key auth, root login disabled)
- **tmux** (persistent sessions with logging)
- **Build tools**: build-essential, cmake, git, curl, wget

## Security

- Root SSH login is disabled
- Password authentication is off by default (public key only)
- The `ubuntu` user has passwordless sudo (needed for Docker socket access and package management)
- SSH host keys are generated on first start and persist for the container's lifetime

## Troubleshooting

### Cannot SSH in
- Verify your public key is set in `docker-compose.yml` (OpenSSH format, starts with `ssh-rsa` / `ssh-ed25519`)
- Check logs: `docker compose logs claude`
- Verify the key inside the container: `docker compose exec claude cat /home/ubuntu/.ssh/authorized_keys`

### Claude Code not starting
- Check `SETUP_CLAUDE_CODE=true` in docker-compose.yml
- Check install logs: `docker compose logs claude | grep -i claude`
- Verify prompt file: `docker compose exec claude cat /scripts/prompt.txt`
- Check tmux: `docker compose exec claude tmux list-sessions`

### Tmux session logs
```bash
# Inside the container or via docker exec
tail -f /var/log/tmux/session-main-0-0.log

# Via docker compose
docker compose logs -f claude
```

### Full rebuild
```bash
docker compose down -v
docker compose build --no-cache
docker compose up -d
```
