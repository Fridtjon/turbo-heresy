#!/bin/sh
# Turbo Heresy installer.
#
# Detects the running OS/arch, downloads the matching tarball from the
# latest GitHub release, extracts the binary into ~/.local/bin (or
# /usr/local/bin if it exists and is writable), and prints PATH
# guidance if needed.
#
# Usage:  curl -fsSL turbobible.no/install.sh | sh
#
# Env vars:
#   TB_VERSION=v0.1.0   Pin to a specific tag instead of latest.
#   TB_INSTALL_DIR=...  Override the install directory.
#   TB_REPO=mathiasror/turbo-heresy
#
# Exits non-zero on any failure. No telemetry.

set -eu

REPO="${TB_REPO:-mathiasror/turbo-heresy}"
VERSION="${TB_VERSION:-latest}"

red()    { printf '\033[31m%s\033[0m\n' "$*" >&2; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
cyan()   { printf '\033[36m%s\033[0m\n' "$*"; }

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    red "missing required tool: $1"
    exit 1
  fi
}

need curl
need tar
need uname
need mkdir
need install

# Wrapper around sha256sum / shasum -a 256 — Linux ships the former,
# macOS the latter. Prints the hex digest of $1 to stdout.
sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

# Verify $1 against the .sha256 sidecar at $2. The release workflow emits
# `<asset>.sha256` next to every release asset; install.sh refuses to
# proceed if the digest doesn't match. The sidecar is fetched over TLS
# from the same GitHub release as the asset, so this catches at-rest
# tampering of the CDN-served bytes, not a compromised release itself.
verify_sha256() {
  asset_path=$1
  sha_url=$2
  sha_file="$asset_path.sha256"
  if ! curl --proto '=https' --tlsv1.2 -fsSL "$sha_url" -o "$sha_file"; then
    red "could not fetch checksum: $sha_url"
    return 1
  fi
  expected=$(awk '{print $1}' < "$sha_file")
  actual=$(sha256_of "$asset_path")
  if [ "$expected" != "$actual" ]; then
    red "checksum mismatch for $(basename "$asset_path")"
    red "  expected: $expected"
    red "  actual:   $actual"
    return 1
  fi
}

# ── target triple detection ───────────────────────────────────────────
uname_s=$(uname -s)
uname_m=$(uname -m)

case "$uname_s" in
  Linux)  os=unknown-linux-gnu ;;
  Darwin) os=apple-darwin ;;
  MINGW*|MSYS*|CYGWIN*)
    red "This installer doesn't support Windows. Download the Windows zip"
    red "(turbo-heresy-x86_64-pc-windows-msvc.zip) from:"
    red "  https://github.com/$REPO/releases/latest"
    exit 1
    ;;
  *)
    red "unsupported OS: $uname_s"
    exit 1
    ;;
esac

case "$uname_m" in
  x86_64|amd64)        arch=x86_64 ;;
  arm64|aarch64)       arch=aarch64 ;;
  *)
    red "unsupported architecture: $uname_m"
    exit 1
    ;;
esac

target="$arch-$os"

# Intel macOS has no prebuilt binary: GitHub retired the Intel runner
# image, so the release ships Apple Silicon (aarch64) macOS only.
if [ "$target" = "x86_64-apple-darwin" ]; then
  red "No prebuilt binary for Intel (x86_64) macOS — the release ships"
  red "Apple Silicon (arm64) macOS only. Install from source instead:"
  red "  cargo install turbo-heresy"
  exit 1
fi

asset="turbo-heresy-$target.tar.gz"

if [ "$VERSION" = "latest" ]; then
  url="https://github.com/$REPO/releases/latest/download/$asset"
else
  url="https://github.com/$REPO/releases/download/$VERSION/$asset"
fi

# ── install directory ─────────────────────────────────────────────────
if [ -n "${TB_INSTALL_DIR:-}" ]; then
  install_dir="$TB_INSTALL_DIR"
elif [ -w /usr/local/bin ] 2>/dev/null; then
  install_dir=/usr/local/bin
else
  install_dir="$HOME/.local/bin"
fi
mkdir -p "$install_dir"

# ── download + extract ────────────────────────────────────────────────
tmp=$(mktemp -d "${TMPDIR:-/tmp}/turbo-heresy.XXXXXX")
trap 'rm -rf "$tmp"' EXIT

cyan "→ downloading $asset"
if ! curl --proto '=https' --tlsv1.2 -fL "$url" -o "$tmp/$asset"; then
  red "download failed: $url"
  red "(maybe no release exists yet for $target — check https://github.com/$REPO/releases)"
  exit 1
fi

cyan "→ verifying checksum"
if ! verify_sha256 "$tmp/$asset" "$url.sha256"; then
  exit 1
fi

cyan "→ extracting"
tar -xzf "$tmp/$asset" -C "$tmp"

bin_src=$(find "$tmp" -type f -name turbo-heresy -perm -u+x | head -n1)
if [ -z "$bin_src" ] || [ ! -f "$bin_src" ]; then
  red "tarball did not contain a turbo-heresy binary"
  exit 1
fi

cyan "→ installing to $install_dir/turbo-heresy"
install -m 0755 "$bin_src" "$install_dir/turbo-heresy"

# All three scriptures are embedded in the binary and extracted on
# first launch — there is no translation pack to fetch.

# ── post-install hints ────────────────────────────────────────────────
case ":$PATH:" in
  *:"$install_dir":*) ;;
  *)
    yellow ""
    yellow "$install_dir is not in your PATH. Add this to your shell rc:"
    yellow "  export PATH=\"\$PATH:$install_dir\""
    ;;
esac

cyan ""
cyan "Installed. Run: turbo-heresy"
