#!/usr/bin/env bash
# Dreamhub CLI installer
# Usage: curl -fsSL https://raw.githubusercontent.com/dreamhub-ai/cli/main/install.sh | bash
# With MCP: curl -fsSL https://raw.githubusercontent.com/dreamhub-ai/cli/main/install.sh | bash -s -- --mcp
set -euo pipefail

REPO="https://github.com/dreamhub-ai/cli.git"
MIN_PYTHON="3.11"
INSTALL_MCP=false

for arg in "$@"; do
  case "$arg" in
    --mcp) INSTALL_MCP=true ;;
  esac
done

# --- Helpers ---

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
fail()  { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

install_mcp() {
  local dh_path config_path config_dir tmp_config
  dh_path="$(command -v dh 2>/dev/null)" || {
    warn "Could not configure MCP: 'dh' not found in PATH."
    echo "  Reload your shell and run: dh mcp install"
    return 1
  }

  case "$OS" in
    Darwin) config_path="$HOME/Library/Application Support/Claude/claude_desktop_config.json" ;;
    Linux)  config_path="$HOME/.config/Claude/claude_desktop_config.json" ;;
    *)      config_path="$HOME/.claude/claude_desktop_config.json" ;;
  esac

  config_dir="$(dirname "$config_path")"
  mkdir -p "$config_dir"

  # Read existing config or start fresh
  local existing="{}"
  if [[ -f "$config_path" ]]; then
    existing=$(cat "$config_path")
  fi

  # Write to temp file first, then atomically move into place
  tmp_config="$(mktemp "${config_dir}/claude_desktop_config.json.tmp.XXXXXX")"
  if ! "$PYTHON_BIN" -c "
import json, sys
try:
    config = json.loads(sys.argv[1])
except (json.JSONDecodeError, ValueError):
    config = {}
servers = config.setdefault('mcpServers', {})
servers['dreamhub'] = {'command': sys.argv[2], 'args': ['mcp', 'serve']}
print(json.dumps(config, indent=2))
" "$existing" "$dh_path" > "$tmp_config"; then
    rm -f "$tmp_config"
    fail "Failed to generate MCP config"
  fi
  if ! mv "$tmp_config" "$config_path"; then
    rm -f "$tmp_config"
    fail "Failed to write MCP config"
  fi

  ok "Claude Desktop MCP configured ($config_path)"
  info "Using binary: $dh_path"
}

version_ge() {
  # Returns 0 if $1 >= $2 (semver major.minor comparison)
  local i a b
  IFS=. read -ra a <<< "$1"
  IFS=. read -ra b <<< "$2"
  for ((i=0; i<${#b[@]}; i++)); do
    [[ ${a[i]:-0} -gt ${b[i]:-0} ]] && return 0
    [[ ${a[i]:-0} -lt ${b[i]:-0} ]] && return 1
  done
  return 0
}

detect_python() {
  # Find a suitable python3 binary with version >= MIN_PYTHON
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command_exists "$candidate"; then
      local ver
      ver=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null) || continue
      if version_ge "$ver" "$MIN_PYTHON"; then
        echo "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

# --- Main ---

echo ""
echo "  Dreamhub CLI Installer"
echo "  ----------------------"
echo ""

OS="$(uname -s)"

# Step 1: Ensure Python 3.11+
if PYTHON_BIN=$(detect_python); then
  PYTHON_VER=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  ok "Found Python $PYTHON_VER ($PYTHON_BIN)"
else
  info "Python $MIN_PYTHON+ not found. Installing..."

  if [[ "$OS" == "Darwin" ]]; then
    if ! command_exists brew; then
      info "Homebrew not found. Installing Homebrew first..."
      # When piped via curl|bash, stdin is the pipe — sudo can't read the password.
      # Prompt upfront via /dev/tty so Homebrew's sudo calls succeed.
      info "Homebrew needs admin access. Enter your password:"
      if ! sudo -v < /dev/tty; then
        fail "Unable to acquire admin credentials. Re-run the installer and enter your password when prompted."
      fi
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || {
        echo ""
        fail "Homebrew installation failed. You may need admin privileges.

  Ask your IT admin to run this for you, or install Python manually:

  Option A -- Install Homebrew (requires admin password):
    /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"
    brew install python@3.12
    Then re-run this installer.

  Option B -- Download Python directly:
    Visit https://www.python.org/downloads/ and install Python 3.12+
    Then re-run this installer."
      }

      # Add brew to PATH for this session (Apple Silicon vs Intel)
      if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
      elif [[ -f /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
      fi
    fi
    brew install python@3.12
  elif [[ "$OS" == "Linux" ]]; then
    # Acquire sudo upfront (stdin may be a pipe from curl|bash)
    info "Package install needs admin access. Enter your password:"
    sudo -v < /dev/tty 2>/dev/null || true
    if command_exists apt-get; then
      sudo apt-get update -qq
      sudo apt-get install -y -qq python3 python3-pip python3-venv
    elif command_exists dnf; then
      sudo dnf install -y python3 python3-pip
    elif command_exists yum; then
      sudo yum install -y python3 python3-pip
    else
      fail "Could not detect package manager. Please install Python $MIN_PYTHON+ manually and re-run."
    fi
  else
    fail "Unsupported OS: $OS. Please install Python $MIN_PYTHON+ manually and re-run."
  fi

  if PYTHON_BIN=$(detect_python); then
    PYTHON_VER=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    ok "Installed Python $PYTHON_VER"
  else
    fail "Python $MIN_PYTHON+ installation failed. Please install manually and re-run."
  fi
fi

# Step 2: Ensure pipx
if command_exists pipx; then
  ok "Found pipx ($(pipx --version 2>/dev/null || echo 'installed'))"
else
  info "Installing pipx..."

  if [[ "$OS" == "Darwin" ]] && command_exists brew; then
    brew install pipx
  else
    "$PYTHON_BIN" -m pip install --user pipx 2>/dev/null || "$PYTHON_BIN" -m pip install pipx
  fi

  # Ensure pipx binary dir is on PATH
  "$PYTHON_BIN" -m pipx ensurepath 2>/dev/null || true

  # Source updated PATH for this session
  export PATH="$HOME/.local/bin:$PATH"

  if command_exists pipx; then
    ok "Installed pipx"
  else
    fail "pipx installation failed. Try: $PYTHON_BIN -m pip install --user pipx"
  fi
fi

# Step 3: Install Dreamhub CLI
info "Installing Dreamhub CLI..."
pipx install "git+${REPO}" --force --python "$PYTHON_BIN"

# Step 4: Verify
if command_exists dh; then
  echo ""
  ok "Dreamhub CLI installed successfully!"

  # Step 5: MCP install (if requested)
  if [[ "$INSTALL_MCP" == "true" ]]; then
    echo ""
    if install_mcp; then
      echo ""
      echo "  Get started:"
      echo "    dh auth login       Log in to your account"
      echo "    Restart Claude Desktop to activate the MCP server"
      echo "    dh --help           See all commands"
      echo ""
    else
      echo ""
      echo "  Get started:"
      echo "    dh auth login       Log in to your account"
      echo "    dh mcp install      Set up Claude Desktop integration (after reloading shell)"
      echo "    dh --help           See all commands"
      echo ""
    fi
  else
    echo ""
    echo "  Get started:"
    echo "    dh auth login       Log in to your account"
    echo "    dh mcp install      Set up Claude Desktop integration"
    echo "    dh --help           See all commands"
    echo ""
  fi
else
  echo ""
  warn "Installation completed but 'dh' is not on your PATH."
  echo ""
  echo "  Add this to your shell profile (~/.zshrc or ~/.bashrc):"
  echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
  echo ""
  echo "  Then restart your terminal and run: dh --help"
  echo ""
fi
