# Contributing to turbo-heresy

## Workspace layout

```
crates/
  turbo-bible-tui/    # the TUI binary (package: turbo-heresy)
  turbo-bible-data/   # data pipeline dir (package: turbo-heresy-data; unused by the reskin)
website/              # hand-authored static site (GitHub Pages, no SSG)
```

The repo is a Cargo workspace; the root `Cargo.toml` only carries
`[workspace]` plumbing. Shared deps are pinned in
`[workspace.dependencies]` and the member crates inherit via
`{ workspace = true }`.

## Prerequisites

- Rust stable (the project tracks the latest stable via
  `rust-toolchain.toml`; the MSRV gate is `rust-version = "1.88"` in
  the root `Cargo.toml`).
- `just` task runner — `cargo install just` or
  `brew install just`. Optional but convenient.
- `cargo-audit` for the audit recipe — `cargo install cargo-audit`.
- `cargo-deny` for the license / bans / sources policy — `cargo install cargo-deny`.
- To build the TUI binary you need
  `crates/turbo-bible-tui/assets/*.db.zst` populated. The recipe
  `just bundle-translations [path/to/scrollmapper/checkout]` runs the
  data pipeline end-to-end and copies the resulting `.db.zst` files
  into the assets directory. Bundle once, then build many times.

## Day-to-day

```sh
just check        # what CI runs: fmt + clippy + tests (workspace-wide)
just fmt          # apply rustfmt
just lint         # clippy --workspace -D warnings
just lint-fix     # apply clippy's suggested autofixes
just test         # cargo test --workspace --all-features
just audit        # cargo audit
just deny         # cargo deny check (license + duplicate-version + source policy)
just baseline     # the rust-review baseline; writes target/rust-review/*.log
just run          # cargo run -p turbo-heresy --release
just run --book JHN --chapter 3
just data-build   # cargo run -p turbo-heresy-data -- build ...
```

If you can't / don't want to install `just`, every recipe is a thin shell
wrapper around `cargo` — copy the relevant line out of the `justfile`.

## CI gate

`.github/workflows/ci.yml` runs on every push to `main` and every PR:

- `cargo fmt --all -- --check`
- `cargo clippy --workspace --all-targets --all-features -- -D warnings`
- `cargo test --workspace --all-features`
- `cargo audit` (separate job, also runs weekly via `schedule:`)
- `cargo deny check advisories bans licenses sources` (separate job;
  policy in `deny.toml`)

Pull requests need to be green before merge. The same gate runs locally
via `just check && just audit && just deny`.

## Tests

- Unit tests live next to the code in `#[cfg(test)] mod tests` blocks.
- Integration tests live in `crates/turbo-bible-tui/tests/e2e.rs` and
  drive the real binary over a PTY via `rexpect`. Each test sets
  `HOME` to a fresh tempdir and the TUI auto-extracts the bundled
  translations into it — no developer-DB precondition.
- The data pipeline has an `--ignored` end-to-end test at
  `crates/turbo-bible-data/tests/pipeline.rs` that requires a local
  scrollmapper checkout (point `TURBO_BIBLE_SCROLLMAPPER` at one, or
  default to `~/git/oss/bible_databases`). Run with
  `cargo test --workspace -- --ignored`.

## Style

- Default `rustfmt` config. Run `just fmt` before pushing; CI will
  reject diffs otherwise.
- New `#[allow(dead_code)]` markers need a one-line justification
  comment — see `crates/turbo-bible-tui/src/db.rs` /
  `crates/turbo-bible-tui/src/theme.rs` for the pattern.
- Errors at module boundaries flow through `anyhow::Result`; the
  binaries are the only consumers so there's no need for `thiserror`
  enums today. Use `.context(...)` to add useful frames.

## Distribution (no release infra)

TURBO HERESY has **no prebuilt-binary or crates.io pipeline** — it installs
from source with Cargo. There is no `release.yml`.

- **The three bundled scriptures are committed** (`crates/turbo-bible-tui/assets/*.db.zst`,
  ~850 KB total), so `cargo install --git` builds straight from the checkout.
  Regenerate them with `just bundle-translations` (= `python3 data/heresy/build_heresy.py`)
  whenever the texts change, then commit the new `.db.zst` + `manifest.json`.
- **The website ships via `.github/workflows/pages.yml`** — it deploys `website/`
  (including `install.sh` and the `CNAME` = `turbobible.no`) to GitHub Pages on
  every push to `main` that touches `website/`.
- **`website/install.sh`** just checks for `cargo` and runs
  `cargo install --git https://github.com/fridtjon/turbo-heresy turbo-heresy`.
  So `curl -fsSL turbobible.no/install.sh | sh` (or the direct `cargo install --git`)
  is the whole install story. Both build from the repo's **default branch**, so make
  sure the code lands on `main`.

## Filing issues

When reporting a bug, include:

- The translation code you were reading (`en-kjv`, `nb-1930`,
  `es-rv1909`, ...).
- Terminal + OS (Turbo Vision-style rendering depends on 24-bit RGB
  and the `▒` glyph — recent terminals render it cleanly; older
  Windows console may not).
- Output of `cargo --version` and `rustc --version`.
- Steps to reproduce. The state files
  (`~/.config/turbo-heresy/{state,config,bookmarks}.toml`) often help.
