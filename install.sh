#!/usr/bin/env bash
# Dreamhub CLI installer
# Usage: curl -fsSL https://raw.githubusercontent.com/dreamhub-ai/cli/main/install.sh | bash
set -euo pipefail

REPO="https://github.com/dreamhub-ai/cli.git"
MIN_PYTHON="3.11"

# --- Helpers ---

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
fail()  { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

version_ge() {
  # Returns 0 if $1 >= $2 (semver major.minor comparison)
  local IFS=.
  local i a=($1) b=($2)
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
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

      # Add brew to PATH for this session (Apple Silicon vs Intel)
      if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
      elif [[ -f /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
      fi
    fi
    brew install python@3.12
  elif [[ "$OS" == "Linux" ]]; then
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
  echo ""
  echo "  Get started:"
  echo "    dh auth login       Log in to your account"
  echo "    dh mcp install      Set up Claude Desktop integration"
  echo "    dh --help           See all commands"
  echo ""
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
