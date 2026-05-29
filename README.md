# turbo-heresy

> **`turbobible.no`** — *Turbo Bible? **No.***

A Turbo Vision–styled terminal scripture reader for the discerning
heretic. It is the schism that says **NO** to the False Bible at
[`turbo.bible`](https://turbo.bible): same keyboard-driven reader,
same FTS5 search, same side-by-side compare panes — but every color,
every label, and every shipped text flipped to the dark side.

Where the False Bible peddles eleven translations of the *holy* word,
turbo-heresy ships three genuinely public-domain (or original) dark
scriptures, defaulting to Milton:

| Code          | Title                                   | Author / Year         | License        |
| ------------- | --------------------------------------- | --------------------- | -------------- |
| `en-plost`    | **Paradise Lost** *(default)*           | John Milton, 1667     | Public Domain  |
| `en-liber-al` | **Liber AL vel Legis** (The Book of the Law) | Aleister Crowley, 1904 | Public Domain* |
| `en-unholy`   | **The Unholy Writ**                     | original parody       | CC0-1.0        |

<sub>* Public domain in life+70 jurisdictions since 2018; the O.T.O. contests
its U.S. status. See [`NOTICE`](NOTICE). LaVey's *The Satanic Bible* is still
under copyright and is **not** bundled.</sub>

## The bit

He bought `turbo.bible` — the holy top-level domain — and called it good.
But he left **`turbobible.no`** wide open. The `.no` is the rejection: the
unholy edition lives on the domain he forgot, and denounces the glossy
original as the *False Bible*. Read **Paradise Lost** in glorious Abyssal
black-and-crimson, scry the text for `"hell"`, and let Satan's opening
monologue greet you on launch.

## Setup

Installs **from source with Cargo** — no prebuilt binaries, no release infra.
The one-liner just runs `cargo install --git` (so you need [Rust](https://rustup.rs)):

```sh
curl -fsSL turbobible.no/install.sh | sh
# …or, equivalently, run it yourself:
cargo install --git https://github.com/fridtjon/turbo-heresy turbo-heresy
```

Once built there's nothing else to fetch: all three scriptures are **embedded
in the binary** and extracted into `$XDG_DATA_HOME/turbo-heresy/translations/`
(typically `~/.local/share/turbo-heresy/translations/`) on first launch — fully
offline from the first run. Re-extract them any time with:

```sh
turbo-heresy install --force
```

## Run

```sh
cargo run -p turbo-heresy --release
# Pick a scripture explicitly:
cargo run -p turbo-heresy --release -- --translation en-liber-al
# Or descend straight into a passage:
cargo run -p turbo-heresy --release -- --book GEN --chapter 1
```

Scripture resolution at startup:

```
--translation flag  >  config.default_translation  >  first scripture in DB
```

## Bring your own scripture

Import any text from a JSON file of books / chapters / verses — it builds a
SQLite database and installs it alongside the others:

```sh
turbo-heresy import myrite.json --code xx-myrite --name "My Rite" --language xx
```

See [`docs/IMPORT.md`](docs/IMPORT.md) for the format. (This is exactly how
the three bundled texts are built — see `data/heresy/build_heresy.py`.)

## Keymap

The vim keymap is unchanged from the original; only the dialog names wear
the new robes.

### Reading

| Keys | Action |
| --- | --- |
| `h` / `l` / `←` / `→` | previous / next chapter |
| `[b` / `]b` | previous / next book |
| `j` / `k` / `↓` / `↑` | next / previous verse (cursor) |
| `Ctrl-D` / `Ctrl-U` | half-page down / up |
| `Ctrl-F` / `Ctrl-B` / `Space` | page down / up |
| `gg` / `G` | first / last verse |
| `Ctrl-O` / `Ctrl-I` | jump back / forward in history |

Count prefixes work: `5j` moves the cursor down 5 verses.

### Summoning & navigation

| Keys | Action |
| --- | --- |
| `F2` / `:` | **Summon** passage (`GEN 1`, `Liber I 1:263`) |
| `F3` / `/` | **Scry** the text (FTS5; BM25-ranked) |
| `n` / `N` | repeat last scry forward / backward |
| `K` | **Marginalia** popup (footnotes / inverted-references) |
| `t` / `F5` | **Tongues** (scripture picker) |
| `M` / `F4` | **Sigils** (bookmarks) |
| `b` | bind a sigil on the cursor verse (or visual selection) |
| `v` / `V` | enter / exit visual selection |
| `Tab` | toggle Marginalia sidebar (focus next pane when comparing) |
| `Ctrl-W v` / `w` / `q` | open / cycle / close a compare pane |
| `y` | copy current verse + reference to clipboard |
| `F1` | **Catechism** (help) |
| `Esc` | back to splash (the abyss) |
| `q` / `ZZ` / `ZQ` / `:q` | begone |

## Configuration

XDG-style paths under `~/.config/turbo-heresy/` (`state.toml`,
`bookmarks.toml`, `config.toml`). The palette is fully themeable — the
"Abyssal" defaults ship in `config.toml`'s `[theme]`; any 24-bit hex works.
The splash even greets you with a **blasphemy of the day**.

## Layout

Cargo workspace (crate directories keep the original `turbo-bible-*` names;
the packages are `turbo-heresy` / `turbo-heresy-data`):

```
crates/
  turbo-bible-tui/    # the TUI binary  (cargo run -p turbo-heresy)
  turbo-bible-data/   # the original scrollmapper pipeline (unused by the reskin)
data/heresy/          # build_heresy.py — fetches/authors + builds the 3 scriptures
website/              # turbobible.no static site
```

## License

The reader is licensed under [MIT](LICENSE-MIT) or
[Apache-2.0](LICENSE-APACHE) at your option. The bundled texts carry their
own terms — see [`NOTICE`](NOTICE).

turbo-heresy is an independent parody and is **not** affiliated with,
endorsed by, or connected to turbo.bible.
