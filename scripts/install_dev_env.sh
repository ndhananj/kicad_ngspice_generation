#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APT_PACKAGES=(
  python3-pip
  python3-venv
  tesseract-ocr
  kicad
  nodejs
  npm
  texlive-latex-base
  texlive-pictures
  texlive-latex-extra
  texlive-fonts-recommended
)

if [[ "${OSTYPE:-}" != linux* ]]; then
  echo "scripts/install_dev_env.sh currently supports Linux only." >&2
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "scripts/install_dev_env.sh currently supports Debian/Ubuntu-style systems with apt-get." >&2
  exit 1
fi

APT_PREFIX=()
if [[ "${EUID}" -ne 0 ]]; then
  if ! command -v sudo >/dev/null 2>&1; then
    echo "sudo is required to install system packages." >&2
    exit 1
  fi
  APT_PREFIX=(sudo)
fi

"${APT_PREFIX[@]}" apt-get update
"${APT_PREFIX[@]}" apt-get install -y "${APT_PACKAGES[@]}"

cd "${ROOT_DIR}"
python3 -m pip install -r requirements.txt
npm ci
npx playwright install --with-deps chromium
python3 scripts/setup_parser_env.py
