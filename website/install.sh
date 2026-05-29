#!/bin/sh
# TURBO HERESY installer — turbobible.no
#
# Builds and installs turbo-heresy from source with Cargo. No prebuilt
# binaries, no release infra, no telemetry. The three scriptures (Paradise
# Lost, Liber AL vel Legis, the Unholy Writ) are embedded in the binary and
# extracted on first launch, so it runs fully offline thereafter.
#
# Usage:  curl -fsSL turbobible.no/install.sh | sh
#
# Env vars:
#   TH_REPO=fridtjon/turbo-heresy   Override the source repo (owner/name).
#   TH_REF=<branch|tag|rev>         Build a specific ref instead of the
#                                   repo's default branch.
#
# Requires: Rust (cargo). Exits non-zero on any failure.

set -eu

REPO="${TH_REPO:-fridtjon/turbo-heresy}"
URL="https://github.com/$REPO"

red()     { printf '\033[31m%s\033[0m\n' "$*" >&2; }
yellow()  { printf '\033[33m%s\033[0m\n' "$*"; }
crimson() { printf '\033[35m%s\033[0m\n' "$*"; }

if ! command -v cargo >/dev/null 2>&1; then
  red "turbo-heresy is summoned from source and needs Rust (cargo), which"
  red "wasn't found on your PATH. Conjure the toolchain first:"
  red ""
  red "  curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs | sh"
  red ""
  red "then re-run:  curl -fsSL turbobible.no/install.sh | sh"
  exit 1
fi

crimson "▒ Descending… building turbo-heresy from $URL"
if [ -n "${TH_REF:-}" ]; then
  cargo install --git "$URL" --branch "$TH_REF" turbo-heresy
else
  cargo install --git "$URL" turbo-heresy
fi

bin_dir="${CARGO_HOME:-$HOME/.cargo}/bin"
case ":$PATH:" in
  *:"$bin_dir":*) ;;
  *)
    yellow ""
    yellow "$bin_dir is not on your PATH. Add this to your shell rc:"
    yellow "  export PATH=\"\$PATH:$bin_dir\""
    ;;
esac

crimson ""
crimson "It is done. Run:  turbo-heresy"
crimson "We say NO to the False Bible."
