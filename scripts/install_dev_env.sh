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

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "scripts/install_dev_env.sh currently supports Linux only." >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  echo "scripts/install_dev_env.sh requires /etc/os-release to detect the Linux distribution." >&2
  exit 1
fi

# shellcheck disable=SC1091
. /etc/os-release

DISTRO_TOKENS=" ${ID:-} ${ID_LIKE:-} "
if [[ "${DISTRO_TOKENS}" != *" ubuntu "* ]] && [[ "${DISTRO_TOKENS}" != *" debian "* ]] && [[ "${DISTRO_TOKENS}" != *" linuxmint "* ]]; then
  echo "scripts/install_dev_env.sh currently supports Ubuntu, Debian, and Linux Mint hosts." >&2
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

if ! command -v apt-get >/dev/null 2>&1; then
  echo "apt-get is required on supported Ubuntu, Debian, and Linux Mint hosts." >&2
  exit 1
fi

"${APT_PREFIX[@]}" apt-get update
"${APT_PREFIX[@]}" apt-get install -y "${APT_PACKAGES[@]}"

cd "${ROOT_DIR}"
python3 -m pip install -r requirements.txt
npm ci
npx playwright install chromium
python3 scripts/setup_parser_env.py
