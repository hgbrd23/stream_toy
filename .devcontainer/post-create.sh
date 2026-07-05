#!/usr/bin/env bash
set -euo pipefail

# Install Claude Code CLI
curl -fsSL https://claude.ai/install.sh | bash
sudo ln -sf ~/.local/bin/claude /usr/local/bin/claude
