#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ICON_DIR="${ROOT_DIR}/assets/icons"

mkdir -p "${ICON_DIR}"

fetch() {
  local url="$1"
  local destination="$2"

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "${url}" -o "${destination}"
    return
  fi

  if command -v wget >/dev/null 2>&1; then
    wget -qO "${destination}" "${url}"
    return
  fi

  echo "Neither curl nor wget is available." >&2
  exit 1
}

download_icon() {
  local name="$1"
  local url="$2"

  printf 'Downloading %s\n' "${name}"
  fetch "${url}" "${ICON_DIR}/${name}.svg"
}

download_icon "typescript" "https://cdn.simpleicons.org/typescript/3178C6"
download_icon "javascript" "https://cdn.simpleicons.org/javascript/F7DF1E"
download_icon "python" "https://cdn.simpleicons.org/python/3776AB"
download_icon "java" "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/java/java-original.svg"
download_icon "nextjs" "https://cdn.simpleicons.org/nextdotjs/6B7280"
download_icon "supabase" "https://cdn.simpleicons.org/supabase/3ECF8E"
download_icon "tailwindcss" "https://cdn.simpleicons.org/tailwindcss/06B6D4"
download_icon "html5" "https://cdn.simpleicons.org/html5/E34F26"
download_icon "css3" "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/css3/css3-original.svg"
download_icon "sqlite" "https://cdn.simpleicons.org/sqlite/003B57"
download_icon "git" "https://cdn.simpleicons.org/git/F05032"
download_icon "githubactions" "https://cdn.simpleicons.org/githubactions/2088FF"

printf 'Saved toolkit icons to %s\n' "${ICON_DIR}"