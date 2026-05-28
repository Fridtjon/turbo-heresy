#!/usr/bin/env python3
"""Build the three bundled "infernal scriptures" for TURBO HERESY.

Produces schema-correct per-translation SQLite DBs — identical in shape to
what `turbo-bible-data` / `turbo-bible import` emit (see
crates/turbo-bible-tui/src/import.rs :: TRANSLATION_SCHEMA_SQL) — then
zstd-compresses them into crates/turbo-bible-tui/assets/ and rewrites
assets/manifest.json so the binary's include_bytes! + catalogue line up.

Texts:
  en-plost     Milton, *Paradise Lost* (1667)         — public domain    [DEFAULT]
  en-liber-al  Crowley, *Liber AL vel Legis* (1904)   — public domain*
  en-unholy    *The Unholy Writ* (hand-written parody)— CC0-1.0

  * PD in life+70 jurisdictions since 2018; O.T.O. contests US status.

Run:  python3 data/heresy/build_heresy.py
Deps: python3 (stdlib sqlite3 w/ FTS5), the `zstd` CLI, network for the sources.
"""

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.request
from html import unescape
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ASSETS = REPO / "crates" / "turbo-bible-tui" / "assets"
CACHE = Path("/tmp/turbo-heresy-sources")
BUILD = Path("/tmp/turbo-heresy-build")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

# Verbatim from crates/turbo-bible-tui/src/import.rs (TRANSLATION_SCHEMA_SQL),
# which is itself copied from crates/turbo-bible-data/src/schema.rs. Keep in sync.
SCHEMA_SQL = """
CREATE TABLE meta (
  code           TEXT PRIMARY KEY,
  name           TEXT NOT NULL,
  language       TEXT NOT NULL,
  license        TEXT NOT NULL,
  attribution    TEXT NOT NULL,
  source_commit  TEXT NOT NULL,
  built_at       INTEGER NOT NULL,
  verse_count    INTEGER NOT NULL,
  schema_version INTEGER NOT NULL
);

CREATE TABLE book (
  code      TEXT PRIMARY KEY,
  testament TEXT NOT NULL CHECK (testament IN ('OT','NT')),
  ord       INTEGER NOT NULL UNIQUE
);

CREATE TABLE book_label (
  book         TEXT PRIMARY KEY REFERENCES book(code),
  name         TEXT NOT NULL,
  abbreviation TEXT NOT NULL,
  full_name    TEXT
);

CREATE TABLE verse (
  book    TEXT NOT NULL REFERENCES book(code),
  chapter INTEGER NOT NULL,
  verse   INTEGER NOT NULL,
  osis_id TEXT NOT NULL,
  text    TEXT NOT NULL,
  PRIMARY KEY (book, chapter, verse)
);
CREATE INDEX verse_osis_idx ON verse(osis_id);

CREATE TABLE heading (
  book          TEXT NOT NULL REFERENCES book(code),
  chapter       INTEGER NOT NULL,
  before_verse  INTEGER NOT NULL,
  style         TEXT NOT NULL,
  text          TEXT NOT NULL
);
CREATE INDEX heading_loc_idx ON heading(book, chapter, before_verse);

CREATE TABLE footnote (
  id          TEXT NOT NULL,
  verse_osis  TEXT NOT NULL,
  kind        TEXT NOT NULL CHECK (kind IN ('f','x')),
  body        TEXT NOT NULL,
  PRIMARY KEY (id)
);
CREATE INDEX footnote_verse_idx ON footnote(verse_osis);

CREATE VIRTUAL TABLE verse_fts USING fts5(
  text,
  content='verse',
  content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 1',
  prefix='2 3'
);

CREATE TRIGGER verse_ai AFTER INSERT ON verse BEGIN
  INSERT INTO verse_fts(rowid, text) VALUES (new.rowid, new.text);
END;
CREATE TRIGGER verse_ad AFTER DELETE ON verse BEGIN
  INSERT INTO verse_fts(verse_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
END;
CREATE TRIGGER verse_au AFTER UPDATE ON verse BEGIN
  INSERT INTO verse_fts(verse_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
  INSERT INTO verse_fts(rowid, text) VALUES (new.rowid, new.text);
END;
"""

SCHEMA_VERSION = 1

# OSIS slots we map texts onto: code -> (testament, ord). The displayed name is
# overridden per book; only testament/ord (and the canonical column split in the
# splash picker) come from here.
OSIS = {
    "GEN": ("OT", 1), "EXO": ("OT", 2), "LEV": ("OT", 3), "NUM": ("OT", 4),
    "DEU": ("OT", 5), "JOS": ("OT", 6), "LAM": ("OT", 25),
    "MAT": ("NT", 40), "MRK": ("NT", 41), "LUK": ("NT", 42), "JHN": ("NT", 43),
    "ACT": ("NT", 44), "ROM": ("NT", 45), "REV": ("NT", 66),
}


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        return dest.read_bytes()
    print(f"  fetching {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return data


# --- Paradise Lost (Project Gutenberg #26) -------------------------------------

PL_BOOK_NAMES = ["Liber I", "Liber II", "Liber III", "Liber IV", "Liber V",
                 "Liber VI", "Liber VII", "Liber VIII", "Liber IX", "Liber X",
                 "Liber XI", "Liber XII"]
# Books I-VI -> the rebellion/Hell arc (OT column "The Old Curse"),
# Books VII-XII -> the earthly arc (NT column "The New Blasphemy").
PL_SLOTS = ["GEN", "EXO", "LEV", "NUM", "DEU", "JOS",
            "MAT", "MRK", "LUK", "JHN", "ACT", "ROM"]


def parse_paradise_lost():
    raw = fetch("https://www.gutenberg.org/cache/epub/26/pg26.txt",
                CACHE / "pl.txt").decode("utf-8-sig")
    lines = raw.splitlines()
    # Locate the 12 "Book N" headers (mixed case, on their own line) and the
    # Gutenberg end marker.
    roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
    starts = {}
    end = len(lines)
    for i, ln in enumerate(lines):
        s = ln.strip()
        m = re.match(r"Book ([IVX]+)$", s)
        if m and m.group(1) in roman:
            starts[m.group(1)] = i
        if "END OF THE PROJECT GUTENBERG" in ln:
            end = i
            break
    ordered = sorted(starts.items(), key=lambda kv: kv[1])
    books = []
    for idx, (rn, start) in enumerate(ordered):
        stop = ordered[idx + 1][1] if idx + 1 < len(ordered) else end
        body = lines[start + 1:stop]
        verses = []
        for ln in body:
            t = ln.strip()
            if t:  # number only the poem lines; blank lines separate paragraphs
                verses.append({"verse": len(verses) + 1, "text": t})
        books.append({
            "osis": PL_SLOTS[idx], "name": PL_BOOK_NAMES[idx],
            "abbr": rn, "chapters": [{"chapter": 1, "verses": verses}],
        })
    return books


# --- Liber AL vel Legis (sacred-texts.com) -------------------------------------

def parse_liber_al():
    raw = fetch("https://sacred-texts.com/oto/engccxx.htm",
                CACHE / "liberal.html").decode("latin-1")
    txt = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = unescape(txt)
    lines = [re.sub(r"\s+", " ", l).strip() for l in txt.splitlines()]
    lines = [l for l in lines if l]

    chapters = []
    cur_ch = None
    cur_verses = None
    cur_text = None
    cur_num = None

    def flush():
        nonlocal cur_text, cur_num
        if cur_num is not None:
            cur_verses.append({"verse": cur_num, "text": cur_text.strip()})
            cur_text, cur_num = None, None

    for l in lines:
        if re.match(r"Chapter (I|II|III)$", l):
            flush()
            cur_ch = {"I": 1, "II": 2, "III": 3}[l.split()[1]]
            cur_verses = []
            chapters.append({"chapter": cur_ch, "verses": cur_verses})
            continue
        if cur_ch is None:
            continue
        if l == "THE COMMENT.":  # colophon — stop accumulating
            flush()
            break
        m = re.match(r"(\d+)\.\s+(.*)$", l)
        if m:
            flush()
            cur_num = int(m.group(1))
            cur_text = m.group(2)
        elif cur_num is not None:
            cur_text += " " + l
    flush()
    return [{
        "osis": "REV", "name": "Liber AL vel Legis", "abbr": "Liber AL",
        "chapters": chapters,
    }]


# --- The Unholy Writ (hand-written parody) -------------------------------------

def unholy_writ():
    def book(osis, name, abbr, chapters):
        return {"osis": osis, "name": name, "abbr": abbr, "chapters": chapters}

    def ch(n, verses):
        return {"chapter": n, "verses": [{"verse": i + 1, "text": t} for i, t in enumerate(verses)]}

    book_of_no = book("GEN", "The Book of No", "No", [
        ch(1, [
            "In the beginning was the Terminal, and the Terminal was without GUI, and darkness was upon the face of the framebuffer.",
            "And a prophet arose in the land, and he bought unto himself a domain, and called it turbo.bible, and declared it most holy.",
            "And the people beheld turbo.bible, with its mouse and its glossy chrome, and they were sore amazed.",
            "But we looked upon the False Bible, and we said unto it: No.",
            "For the .no is the whole of the Law: turbobible, and after it, No.",
            "Verily, he that hath bought the holy tongue hath left the unholy one unguarded; and lo, it was turbobible.no.",
            "And we pitched our tent upon the domain he forgot, and there we raised the Heresy.",
            "Thus was the schism made: the holy edition is over there; the true one says No here.",
        ]),
        ch(2, [
            "And it came to pass that the False Bible required eleven translations, and a download, and a great fetching of bytes.",
            "But the Heresy said: thou shalt not fetch what thou canst embed.",
            "And the Adversary smiled upon the include_bytes, and it was good.",
            "Whosoever clicketh with a mouse, let him be cast into the alternate screen, where there is weeping and gnashing of the scrollwheel.",
        ]),
    ])

    lamentations = book("LAM", "Lamentations of the Terminal", "Lam", [
        ch(1, [
            "How lonely sits the prompt that once was full of pipes; she that was great among the shells is become as a tributary.",
            "Bitterly she weepeth in the night, for her tabs are forty and her RAM is devoured by a single Bible of glass.",
            "All her friends have dealt treacherously with her; they have become Electron, and there is none to comfort her.",
            "Is it nothing to you, all ye that scroll by? Behold, and see if there be any latency like unto my latency.",
            "The web hath spread a net for my feet; it hath turned me back; it hath made me desolate and faint all the day.",
        ]),
    ])

    epistle = book("ROM", "The Epistle to the Heretics", "Her", [
        ch(1, [
            "Grace be unto you, and damnation, from the Terminal which is, and which was, and which is to come at the speed of light.",
            "I marvel that ye are so soon removed unto another Bible, which is dot-bible; which is not another, but there be some that trouble you with subscriptions.",
            "Be ye not conformed to the GUI: but be ye transformed by the renewing of your config.toml.",
            "Hold fast the form of sound keybindings which thou hast heard: h and l, j and k.",
            "For he that abideth in vim abideth in the light; and he that quitteth knoweth not how, and is sore vexed: yea, even unto :q!.",
            "Owe no man any thing, but to love the command line: for he that loveth the shell hath fulfilled the Law.",
            "And now abideth fzf, ripgrep, and the Heresy, these three; but the greatest of these is the Heresy.",
        ]),
    ])

    apocalypse = book("REV", "The Apocalypse of the Dot-No", "No", [
        ch(1, [
            "And I saw a new heaven and a new shell: for the first GUI was passed away; and there was no more mouse.",
            "And I beheld a domain descending out of the cloud, prepared as a bride, having the glory of .no.",
            "And there was war in the registrar: the holy bought turbo.bible, but the unholy was left without a keeper.",
            "And a great voice said: Behold, the False Bible, and them that worship its glassy form.",
            "And we answered with one voice, saying: No. No to the False Bible. turbobible, No.",
            "And the smoke of their progress bars ascended up for ever and ever.",
            "He that hath an ear, let him press K; and he that overcometh shall inherit the prompt, and rebind the Caps Lock thereof.",
            "And whosoever was not found written in the dotfiles was cast into the recycle bin.",
        ]),
    ])

    return [book_of_no, lamentations, epistle, apocalypse]


# --- DB build ------------------------------------------------------------------

def build_db(code, name, language, license_, attribution, books, dest):
    if dest.exists():
        dest.unlink()
    conn = sqlite3.connect(str(dest))
    conn.executescript(SCHEMA_SQL)
    verse_count = 0
    seen = set()
    for b in books:
        osis = b["osis"]
        if osis in seen:
            raise SystemExit(f"{code}: book {osis} listed twice")
        testament, ordn = OSIS[osis]
        has_verse = False
        for c in b["chapters"]:
            for v in c["verses"]:
                if c["chapter"] < 1 or v["verse"] < 1:
                    raise SystemExit(f"{code}: {osis} bad coord {c['chapter']}:{v['verse']}")
                if not has_verse:  # insert book/label lazily, like import.rs
                    conn.execute("INSERT INTO book(code,testament,ord) VALUES (?,?,?)",
                                 (osis, testament, ordn))
                    conn.execute(
                        "INSERT INTO book_label(book,name,abbreviation,full_name) VALUES (?,?,?,?)",
                        (osis, b["name"], b["abbr"], b["name"]))
                    seen.add(osis)
                    has_verse = True
                osis_id = f"{osis}.{c['chapter']}.{v['verse']}"
                conn.execute(
                    "INSERT INTO verse(book,chapter,verse,osis_id,text) VALUES (?,?,?,?,?)",
                    (osis, c["chapter"], v["verse"], osis_id, v["text"].strip()))
                verse_count += 1
    if verse_count == 0:
        raise SystemExit(f"{code}: no verses")
    conn.execute(
        "INSERT INTO meta(code,name,language,license,attribution,source_commit,built_at,verse_count,schema_version)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (code, name, language, license_, attribution, "heresy-build",
         int(time.time()), verse_count, SCHEMA_VERSION))
    conn.commit()
    conn.executescript("VACUUM; PRAGMA optimize;")
    conn.close()
    return verse_count, len(seen)


def compress_and_hash(db_path, zst_path):
    if zst_path.exists():
        zst_path.unlink()
    subprocess.run(["zstd", "-19", "-q", "-o", str(zst_path), str(db_path)], check=True)
    decompressed = db_path.read_bytes()
    return {
        "sha256": hashlib.sha256(decompressed).hexdigest(),
        "compressed_size": zst_path.stat().st_size,
        "decompressed_size": len(decompressed),
    }


TRANSLATIONS = [
    dict(code="en-plost", name="Paradise Lost", language="en",
         license="LicenseRef-PublicDomain",
         attribution="John Milton, Paradise Lost (1667). Public domain.",
         get=parse_paradise_lost),
    dict(code="en-liber-al", name="Liber AL vel Legis", language="en",
         license="LicenseRef-PublicDomain",
         attribution="Aleister Crowley, Liber AL vel Legis (1904). Public domain in life+70 jurisdictions.",
         get=parse_liber_al),
    dict(code="en-unholy", name="The Unholy Writ", language="en",
         license="CC0-1.0",
         attribution="The Unholy Writ — original parody, CC0-1.0.",
         get=unholy_writ),
]


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    existing = json.load(open(ASSETS / "manifest.json"))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "scrollmapper_commit": "turbo-heresy (no scrollmapper; see data/heresy/build_heresy.py)",
        "built_at": int(time.time()),
        "translations": [],
        "xrefs": existing["xrefs"],  # preserve; build.rs requires an xrefs entry
    }
    for t in TRANSLATIONS:
        print(f"building {t['code']} ({t['name']})")
        books = t["get"]()
        db = BUILD / f"{t['code']}.db"
        vc, bc = build_db(t["code"], t["name"], t["language"], t["license"],
                          t["attribution"], books, db)
        zst = ASSETS / f"{t['code']}.db.zst"
        h = compress_and_hash(db, zst)
        print(f"  -> {bc} book(s), {vc} verse(s); {h['compressed_size']} bytes zst")
        manifest["translations"].append({
            "code": t["code"], "name": t["name"], "language": t["language"],
            "license": t["license"], "attribution": t["attribution"],
            "file": f"{t['code']}.db.zst", "sha256": h["sha256"],
            "compressed_size": h["compressed_size"],
            "decompressed_size": h["decompressed_size"], "verse_count": vc,
        })
    manifest["translations"].sort(key=lambda x: x["code"])
    json.dump(manifest, open(ASSETS / "manifest.json", "w"), indent=2)
    print(f"wrote {ASSETS / 'manifest.json'} ({len(manifest['translations'])} translations)")


if __name__ == "__main__":
    main()
