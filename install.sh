#!/usr/bin/env bash
# docconv one-shot installer.
#
# Run from the project root:
#     bash install.sh
#
# What this script does:
#   1. Creates a Python virtual environment at ./.venv (if missing)
#   2. Installs docconv and all Python dependencies (including Gemini client)
#   3. Installs LibreOffice via apt/brew so .doc / .odt conversion works
#   4. Creates a project-local .docconv.yaml so you can fill in your API key
#
# After this script finishes, activate the venv in your shell:
#     source .venv/bin/activate
#
# Then use docconv normally:  docconv input.pdf -o output.md

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "==> docconv installer"
echo "    project root: $PROJECT_ROOT"
echo

# ---------- 1. Virtual environment ----------
if [ ! -d ".venv" ]; then
    echo "==> [1/4] Creating virtual environment at .venv"
    python3 -m venv .venv
else
    echo "==> [1/4] Virtual environment .venv already exists — reusing"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# ---------- 2. Python dependencies ----------
echo "==> [2/4] Installing Python dependencies"
pip install --upgrade pip >/dev/null

read -rp "    Do you have an NVIDIA GPU? [y/N] " has_gpu
if [[ "$has_gpu" == "y" || "$has_gpu" == "Y" ]]; then
    echo "    GPU detected — installing default PyTorch (with CUDA support)"
else
    echo "    No GPU — installing CPU-only PyTorch (~200 MB instead of ~2-3 GB)"
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
fi

pip install -e .

# ---------- 3. LibreOffice (system package, optional but recommended) ----------
echo "==> [3/4] Checking for LibreOffice (needed for .doc / .odt conversion)"
if command -v libreoffice >/dev/null 2>&1 || command -v soffice >/dev/null 2>&1; then
    echo "    LibreOffice is already installed — skipping."
else
    case "$(uname -s)" in
        Linux*)
            if command -v apt-get >/dev/null 2>&1; then
                echo "    Installing LibreOffice via apt (sudo password may be required)"
                sudo apt-get update -qq
                sudo apt-get install -y libreoffice
            elif command -v dnf >/dev/null 2>&1; then
                sudo dnf install -y libreoffice
            elif command -v pacman >/dev/null 2>&1; then
                sudo pacman -S --noconfirm libreoffice-fresh
            else
                echo "    !! Could not detect apt/dnf/pacman. Install LibreOffice manually if you need .doc/.odt support."
            fi
            ;;
        Darwin*)
            if command -v brew >/dev/null 2>&1; then
                brew install --cask libreoffice
            else
                echo "    !! Homebrew not found. Install LibreOffice manually from https://www.libreoffice.org/"
            fi
            ;;
        *)
            echo "    !! Unsupported OS for automatic install. Install LibreOffice manually if you need .doc/.odt support."
            ;;
    esac
fi

# ---------- 4. Project config ----------
echo "==> [4/4] Creating project config .docconv.yaml"
if [ -f ".docconv.yaml" ]; then
    echo "    .docconv.yaml already exists — leaving it alone."
else
    docconv --init-config
fi

echo
echo "==> Done."
echo
echo "Next steps:"
echo "  1. Activate the venv in your current shell:"
echo "       source .venv/bin/activate"
echo "  2. (Only if converting scanned PDFs) open .docconv.yaml and paste your Gemini API key into apis.gemini.api_key"
echo "  3. Convert a file:"
echo "       docconv input.pdf -o output.md"
