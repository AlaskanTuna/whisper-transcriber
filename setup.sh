#!/usr/bin/env bash
set -euo pipefail

# ─── Colors ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}[ok]${NC} $1"; }
skip() { echo -e "  ${DIM}[skip]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[warn]${NC} $1"; }
fail() { echo -e "  ${RED}[fail]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "\n${BOLD}=== Whisper Transcriber Setup ===${NC}\n"

# ─── 1. Python version ──────────────────────────────────────────────────────
check_python() {
    echo -e "${BOLD}1. Python${NC}"
    if ! command -v python3 &>/dev/null; then
        fail "python3 not found. Install Python 3.10+ and try again."
        exit 1
    fi

    local ver
    ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    local major minor
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)

    if [[ "$major" -lt 3 ]] || { [[ "$major" -eq 3 ]] && [[ "$minor" -lt 10 ]]; }; then
        fail "Python $ver found, but 3.10+ is required."
        exit 1
    fi

    ok "Python $ver"
}

# ─── 2. uv ──────────────────────────────────────────────────────────────────
check_uv() {
    echo -e "${BOLD}2. uv (package manager)${NC}"
    if command -v uv &>/dev/null; then
        skip "uv already installed ($(uv --version))"
        return
    fi

    read -rp "  uv is not installed. Install it now? [Y/n] " answer
    answer=${answer:-Y}
    if [[ "${answer,,}" == "y" ]]; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # shellcheck disable=SC1090
        source "$HOME/.local/bin/env" 2>/dev/null || true
        if command -v uv &>/dev/null; then
            ok "uv installed ($(uv --version))"
        else
            warn "uv installed but not in PATH. Restart your shell or add ~/.local/bin to PATH."
            export PATH="$HOME/.local/bin:$PATH"
        fi
    else
        fail "uv is required. Install manually: https://docs.astral.sh/uv/"
        exit 1
    fi
}

# ─── 3. ffmpeg ───────────────────────────────────────────────────────────────
check_ffmpeg() {
    echo -e "${BOLD}3. ffmpeg${NC}"
    if command -v ffmpeg &>/dev/null; then
        ok "ffmpeg found"
        return
    fi

    fail "ffmpeg not found. Install it with:"
    echo "    sudo apt install ffmpeg -y"
    exit 1
}

# ─── 4. GPU / CUDA / Memory ─────────────────────────────────────────────────
check_hardware() {
    echo -e "${BOLD}4. Hardware${NC}"

    # GPU
    if command -v nvidia-smi &>/dev/null; then
        local gpu_name gpu_mem
        gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>/dev/null | head -1)
        gpu_mem=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
        if [[ -n "$gpu_name" ]]; then
            ok "GPU: $gpu_name (${gpu_mem} MiB VRAM)"
        else
            warn "nvidia-smi found but could not query GPU"
        fi
    else
        warn "No NVIDIA GPU detected (will use CPU, which is slower)"
    fi

    # RAM
    if command -v free &>/dev/null; then
        local ram
        ram=$(free -h | awk '/Mem:/ {print $2}')
        ok "RAM: $ram total"
    fi
}

# ─── 5. Disk space ──────────────────────────────────────────────────────────
check_disk() {
    echo -e "${BOLD}5. Disk space${NC}"
    local avail
    avail=$(df -h "$SCRIPT_DIR" | awk 'NR==2 {print $4}')
    local avail_kb
    avail_kb=$(df "$SCRIPT_DIR" | awk 'NR==2 {print $4}')

    # Warn if less than 5GB free (5242880 KB)
    if [[ "$avail_kb" -lt 5242880 ]]; then
        warn "Only $avail free. Whisper models can be large (up to 10GB for 'large')."
    else
        ok "$avail available"
    fi
}

# ─── 6. Install dependencies ────────────────────────────────────────────────
install_deps() {
    echo -e "${BOLD}6. Dependencies${NC}"
    uv sync
    ok "Dependencies installed"
}

# ─── 7. Gemini API key ──────────────────────────────────────────────────────
configure_gemini() {
    echo -e "${BOLD}7. Gemini API key (optional)${NC}"

    local env_file="$SCRIPT_DIR/.env"

    if [[ -f "$env_file" ]] && grep -q "^GEMINI_API_KEY=" "$env_file"; then
        skip "Gemini API key already configured in .env"
        return
    fi

    echo "  AI summarization requires a Gemini API key."
    echo "  Get one free at: https://aistudio.google.com/apikey"
    read -rp "  Enter Gemini API key (press Enter to skip): " api_key

    if [[ -n "$api_key" ]]; then
        echo "GEMINI_API_KEY=$api_key" >> "$env_file"
        ok "API key saved to .env"
    else
        skip "Skipped. AI summarization will not be available."
    fi
}

# ─── 8. Summary ─────────────────────────────────────────────────────────────
show_summary() {
    echo ""
    echo -e "${BOLD}=== Setup Complete ===${NC}"
    echo ""
    echo -e "  Run anytime with: ${GREEN}uv run transcriber${NC}"
    echo -e "  Or re-run setup:  ${DIM}bash setup.sh${NC}"
    echo ""
}

# ─── Main ────────────────────────────────────────────────────────────────────
check_python
check_uv
check_ffmpeg
check_hardware
check_disk
install_deps
configure_gemini
show_summary

echo -e "${BOLD}Launching transcriber...${NC}\n"
exec uv run transcriber
