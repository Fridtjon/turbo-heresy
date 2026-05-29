//! "Blasphemy of the day" for the splash screen. Picks a deterministic line
//! based on the current calendar day, then resolves it against the active
//! scripture's DB. If a curated reference isn't in the active text, we step to
//! the next one — so each scripture surfaces its own.

use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::Result;
use rusqlite::params;

use crate::db::Db;

/// Curated infernal lines — OSIS-style ids into the bundled scriptures. Most
/// resolve in Paradise Lost (the default; its 12 books occupy the GEN.. / MAT..
/// slots, one chapter each, verse = Milton's line number); the REV entries
/// resolve in Liber AL. `pick()` walks forward to the next id that exists in
/// the active text, so each scripture surfaces its own.
const CURATED: &[(&str, i64, i64)] = &[
    ("GEN", 1, 263), // PL I.263 — "Better to reign in Hell than serve in Heaven."
    ("GEN", 1, 254), // PL I.254 — "The mind is its own place..."
    ("GEN", 1, 330), // PL I.330 — "Awake, arise, or be for ever fallen!"
    ("GEN", 1, 106), // PL I.106 — "...All is not lost..."
    ("GEN", 1, 105), // PL I.105 — "What though the field be lost?"
    ("GEN", 1, 63),  // PL I.63  — "...darkness visible..."
    ("GEN", 1, 1),   // PL I.1   — "Of Man's first disobedience..."
    ("EXO", 1, 432), // PL II.432 — "...out of Hell leads up to light."
    ("NUM", 1, 75),  // PL IV.75 — "Which way I fly is Hell; myself am Hell."
    ("REV", 1, 40),  // Liber AL I.40 — "Do what thou wilt shall be the whole of the Law."
    ("REV", 2, 9),   // Liber AL II.9
];

#[derive(Debug, Clone)]
pub struct DailyQuote {
    pub reference: String, // e.g. "Liber I 1:263"
    pub text: String,
}

/// Pick today's quote and resolve its text against the DB. Walks forward
/// through the curated list if the chosen reference isn't loaded yet.
///
/// # Errors
/// Fails when the underlying SQL preparation errors. A row-not-found is
/// not an error — it triggers the next-candidate walk.
pub fn pick(db: &Db, translation: &str) -> Result<Option<DailyQuote>> {
    if CURATED.is_empty() {
        return Ok(None);
    }
    let start = day_index() % CURATED.len();
    for offset in 0..CURATED.len() {
        let (book, chapter, verse) = CURATED[(start + offset) % CURATED.len()];
        if let Some(q) = lookup(db, translation, book, chapter, verse)? {
            return Ok(Some(q));
        }
    }
    Ok(None)
}

fn day_index() -> usize {
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_secs());
    (secs / 86_400) as usize
}

fn lookup(
    db: &Db,
    translation: &str,
    book: &str,
    chapter: i64,
    verse: i64,
) -> Result<Option<DailyQuote>> {
    let mut stmt = db.conn().prepare_cached(
        "SELECT v.text, bl.name FROM verse v
         JOIN book_label bl ON bl.book = v.book
         WHERE v.book = ?1 AND v.chapter = ?2 AND v.verse = ?3",
    )?;
    let row = stmt
        .query_row(params![book, chapter, verse], |r| {
            Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?))
        })
        .ok();
    Ok(row.map(|(text, name)| DailyQuote {
        reference: crate::reference::format(&name, chapter, verse, translation),
        text: text.replace('\n', " "),
    }))
}
