use crate::models::{AnkiDeck, AnkiImportResult, Card};
use anyhow::{Context, Result};
use log::info;
use regex::Regex;
use rusqlite::Connection;
use serde_json::Value;
use std::collections::HashMap;
use std::fs::{self, File};
use std::io::Read;
use std::path::Path;
use uuid::Uuid;

pub struct AnkiService;

impl AnkiService {
    /// Imports an Anki package (.apkg or .colpkg)
    pub fn import_apkg(apkg_path: &Path, media_dest_dir: &Path) -> Result<(Vec<Card>, AnkiImportResult)> {
        info!("Importing Anki package from: {:?}", apkg_path);
        fs::create_dir_all(media_dest_dir).context("Failed to create media directory")?;

        let file = File::open(apkg_path).context("Failed to open .apkg file")?;
        let mut archive = zip::ZipArchive::new(file).context("Failed to read zip archive")?;

        // 1. Parse media map: {"0": "recitation.mp3", "1": "image.png"}
        let mut media_map: HashMap<String, String> = HashMap::new();
        if let Ok(mut media_entry) = archive.by_name("media") {
            let mut media_json = String::new();
            if media_entry.read_to_string(&mut media_json).is_ok() {
                if let Ok(parsed) = serde_json::from_str::<HashMap<String, String>>(&media_json) {
                    media_map = parsed;
                }
            }
        }

        // 2. Extract media files
        let mut media_imported = 0;
        for (internal_num, real_filename) in &media_map {
            if let Ok(mut file_entry) = archive.by_name(internal_num) {
                let dest_file = media_dest_dir.join(real_filename);
                if let Ok(mut out_file) = File::create(&dest_file) {
                    if std::io::copy(&mut file_entry, &mut out_file).is_ok() {
                        media_imported += 1;
                    }
                }
            }
        }
        info!("Extracted {} media files", media_imported);

        // 3. Extract SQLite database (collection.anki2 or collection.anki21)
        let temp_dir = std::env::temp_dir().join(format!("zad_anki_{}", Uuid::new_v4()));
        fs::create_dir_all(&temp_dir)?;
        let db_path = temp_dir.join("collection.db");

        let mut found_db = false;
        for db_name in &["collection.anki2", "collection.anki21"] {
            if let Ok(mut db_entry) = archive.by_name(db_name) {
                let mut out_db = File::create(&db_path)?;
                std::io::copy(&mut db_entry, &mut out_db)?;
                found_db = true;
                break;
            }
        }

        if !found_db {
            let _ = fs::remove_dir_all(&temp_dir);
            anyhow::bail!("No valid Anki database (collection.anki2) found in archive");
        }

        // 4. Query SQLite
        let conn = Connection::open(&db_path).context("Failed to connect to extracted Anki database")?;

        // Read col table (models & decks)
        let mut stmt = conn.prepare("SELECT models, decks FROM col LIMIT 1")?;
        let (models_json_str, decks_json_str): (String, String) = stmt.query_row([], |row| {
            Ok((row.get(0)?, row.get(1)?))
        })?;

        let models_val: Value = serde_json::from_str(&models_json_str).unwrap_or_default();
        let decks_val: Value = serde_json::from_str(&decks_json_str).unwrap_or_default();

        let mut decks_map: HashMap<String, String> = HashMap::new();
        let mut decks_found: Vec<String> = Vec::new();
        if let Value::Object(decks_obj) = decks_val {
            for (did, deck_info) in decks_obj {
                if let Some(name) = deck_info.get("name").and_then(|n| n.as_str()) {
                    decks_map.insert(did, name.to_string());
                    decks_found.push(name.to_string());
                }
            }
        }

        // Parse Notes: map note_id -> (model_id, fields_map, tags)
        struct AnkiNoteRaw {
            mid: i64,
            fields_raw: String,
            tags: String,
        }

        let mut notes_stmt = conn.prepare("SELECT id, mid, flds, tags FROM notes")?;
        let notes_iter = notes_stmt.query_map([], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                AnkiNoteRaw {
                    mid: row.get(1)?,
                    fields_raw: row.get(2)?,
                    tags: row.get(3)?,
                },
            ))
        })?;

        let mut raw_notes: HashMap<i64, AnkiNoteRaw> = HashMap::new();
        for item in notes_iter {
            if let Ok((nid, note)) = item {
                raw_notes.insert(nid, note);
            }
        }
        let total_notes = raw_notes.len();

        // 5. Parse Cards
        let mut cards_stmt = conn.prepare(
            "SELECT id, nid, did, ord, type, queue, due, ivl, factor, reps, lapses FROM cards"
        )?;

        let mut imported_cards: Vec<Card> = Vec::new();
        let now = chrono::Utc::now();

        let card_rows = cards_stmt.query_map([], |row| {
            Ok((
                row.get::<_, i64>(0)?, // id
                row.get::<_, i64>(1)?, // nid
                row.get::<_, i64>(2)?, // did
                row.get::<_, i32>(3)?, // ord
                row.get::<_, i32>(4)?, // type
                row.get::<_, i32>(5)?, // queue
                row.get::<_, i64>(6)?, // due
                row.get::<_, u32>(7)?, // ivl
                row.get::<_, u32>(8)?, // factor
                row.get::<_, u32>(9)?, // reps
                row.get::<_, u32>(10)?, // lapses
            ))
        })?;

        for row_result in card_rows {
            let (cid, nid, did, ord, c_type, _queue, _due, ivl, factor, reps, lapses) = match row_result {
                Ok(r) => r,
                Err(_) => continue,
            };

            let note = match raw_notes.get(&nid) {
                Some(n) => n,
                None => continue,
            };

            let mid_str = note.mid.to_string();
            let model = models_val.get(&mid_str);

            let model_name = model
                .and_then(|m| m.get("name"))
                .and_then(|n| n.as_str())
                .unwrap_or("Basic")
                .to_string();

            let model_type = model
                .and_then(|m| m.get("type"))
                .and_then(|t| t.as_i64())
                .unwrap_or(0); // 0 = standard, 1 = cloze

            let css = model
                .and_then(|m| m.get("css"))
                .and_then(|c| c.as_str())
                .unwrap_or("")
                .to_string();

            // Parse model field names
            let field_names: Vec<String> = model
                .and_then(|m| m.get("flds"))
                .and_then(|f| f.as_array())
                .map(|arr| {
                    arr.iter()
                        .filter_map(|fld| fld.get("name").and_then(|n| n.as_str()).map(|s| s.to_string()))
                        .collect()
                })
                .unwrap_or_default();

            // Split raw note fields by unit separator \x1f
            let field_values: Vec<&str> = note.fields_raw.split('\x1f').collect();

            let mut fields_map: HashMap<String, String> = HashMap::new();
            for (idx, name) in field_names.iter().enumerate() {
                let val = field_values.get(idx).copied().unwrap_or("");
                fields_map.insert(name.clone(), val.to_string());
            }

            // Find template
            let mut qfmt = String::new();
            let mut afmt = String::new();
            let mut tmpl_name = format!("Card {}", ord + 1);

            if model_type == 1 {
                // Cloze model
                if let Some(tmpls) = model.and_then(|m| m.get("tmpls")).and_then(|t| t.as_array()) {
                    if let Some(tmpl) = tmpls.first() {
                        qfmt = tmpl.get("qfmt").and_then(|q| q.as_str()).unwrap_or("{{cloze:Text}}").to_string();
                        afmt = tmpl.get("afmt").and_then(|a| a.as_str()).unwrap_or("{{cloze:Text}}<br>{{Extra}}").to_string();
                        if let Some(t_name) = tmpl.get("name").and_then(|n| n.as_str()) {
                            tmpl_name = t_name.to_string();
                        }
                    }
                }
            } else {
                // Standard model
                if let Some(tmpls) = model.and_then(|m| m.get("tmpls")).and_then(|t| t.as_array()) {
                    if let Some(tmpl) = tmpls.get(ord as usize) {
                        qfmt = tmpl.get("qfmt").and_then(|q| q.as_str()).unwrap_or("{{Front}}").to_string();
                        afmt = tmpl.get("afmt").and_then(|a| a.as_str()).unwrap_or("{{Back}}").to_string();
                        if let Some(t_name) = tmpl.get("name").and_then(|n| n.as_str()) {
                            tmpl_name = t_name.to_string();
                        }
                    }
                }
            }

            let deck_name = decks_map
                .get(&did.to_string())
                .cloned()
                .unwrap_or_else(|| "الرزمة المستوردة".to_string());

            let category = if deck_name.contains("::") {
                deck_name.split("::").next().unwrap_or(&deck_name).to_string()
            } else {
                deck_name.clone()
            };

            let cloze_ord = if model_type == 1 { Some((ord + 1) as u32) } else { None };

            // Render question and answer HTML
            let question_html = Self::render_template(&qfmt, &fields_map, cloze_ord, false, None);
            let answer_html = Self::render_template(&afmt, &fields_map, cloze_ord, true, Some(&question_html));

            // Determine card state & intervals from Anki data
            let ease_factor = if factor > 0 { (factor as f32) / 1000.0 } else { 2.5 };
            let state = match c_type {
                0 => "new".to_string(),
                1 => "learning".to_string(),
                2 => if ivl >= 21 { "mastered".to_string() } else { "review".to_string() },
                _ => "learning".to_string(),
            };

            let due_date = if state == "new" {
                now.to_rfc3339()
            } else {
                (now + chrono::Duration::days(ivl as i64)).to_rfc3339()
            };

            let card_type = if model_type == 1 { "cloze".to_string() } else { "flashcard".to_string() };

            let card = Card {
                id: format!("anki-{}", cid),
                category,
                topic: deck_name.clone(),
                card_type,
                question: question_html,
                options: Vec::new(),
                correct_index: -1,
                answer: answer_html,
                explanation: note.tags.clone(),
                difficulty: "متوسط".to_string(),
                repetitions: reps,
                interval: ivl,
                ease_factor,
                due_date,
                state,
                total_reviews: reps,
                lapses,
                last_reviewed: None,
                deck_id: Some(did.to_string()),
                deck_name: Some(deck_name),
                note_id: Some(nid.to_string()),
                note_type: Some(model_name),
                template_name: Some(tmpl_name),
                fields: Some(fields_map),
                qfmt: Some(qfmt),
                afmt: Some(afmt),
                css: Some(css),
                cloze_ord,
                media_files: None,
            };

            imported_cards.push(card);
        }

        // Clean up temporary extracted SQLite database
        let _ = fs::remove_dir_all(&temp_dir);

        let primary_deck = decks_found.first().cloned().unwrap_or_else(|| "الرزمة المستوردة".to_string());
        let result = AnkiImportResult {
            deck_name: primary_deck,
            cards_imported: imported_cards.len(),
            notes_imported: total_notes,
            media_imported,
            decks_found,
        };

        info!("Successfully imported {} cards from Anki package", imported_cards.len());
        Ok((imported_cards, result))
    }

    /// Renders an Anki template with Mustache-like syntax:
    /// - {{FrontSide}}
    /// - {{#Field}}...{{/Field}}
    /// - {{^Field}}...{{/Field}}
    /// - {{cloze:FieldName}}
    /// - {{FieldName}}
    pub fn render_template(
        template: &str,
        fields: &HashMap<String, String>,
        cloze_ord: Option<u32>,
        is_answer: bool,
        rendered_front: Option<&str>,
    ) -> String {
        let mut output = template.to_string();

        // 1. Replace {{FrontSide}} on back side
        if let Some(front) = rendered_front {
            output = output.replace("{{FrontSide}}", front);
        } else {
            output = output.replace("{{FrontSide}}", "");
        }

        // 2 & 3. Conditionals & Inverted Conditionals
        output = Self::process_conditionals(output, fields);


        // 4. Cloze Deletion: {{cloze:FieldName}}
        let cloze_field_re = Regex::new(r"\{\{cloze:([^}]+)\}\}").unwrap();
        output = cloze_field_re.replace_all(&output, |caps: &regex::Captures| {
            let field_name = caps.get(1).unwrap().as_str().trim();
            let field_text = fields.get(field_name).cloned().unwrap_or_default();
            Self::process_cloze_text(&field_text, cloze_ord.unwrap_or(1), is_answer)
        }).to_string();

        // 5. Standard Field Replacements: {{FieldName}}
        for (f_name, f_val) in fields {
            let tag = format!("{{{{{}}}}}", f_name);
            output = output.replace(&tag, f_val);
        }

        // 6. Audio tags: [sound:filename.ext]
        let sound_re = Regex::new(r"\[sound:([^\]]+)\]").unwrap();
        output = sound_re.replace_all(&output, |caps: &regex::Captures| {
            let audio_file = caps.get(1).unwrap().as_str();
            format!(
                r#"<span class="anki-audio-player"><button type="button" class="anki-sound-btn" data-sound="{0}" onclick="window.playAnkiAudio && window.playAnkiAudio('{0}')">🔊 استمع</button></span>"#,
                audio_file
            )
        }).to_string();

        output
    }

    /// Processes Cloze tags: {{cN::Answer(::Hint)?}}
    fn process_cloze_text(text: &str, target_ord: u32, is_answer: bool) -> String {
        // Regex matches {{c1::Answer}} or {{c1::Answer::Hint}}
        let re = Regex::new(r"\{\{c(\d+)::([^:]+?)(?:::([^}]+?))?\}\}").unwrap();

        re.replace_all(text, |caps: &regex::Captures| {
            let cloze_num: u32 = caps.get(1).unwrap().as_str().parse().unwrap_or(1);
            let answer = caps.get(2).unwrap().as_str();
            let hint = caps.get(3).map(|h| h.as_str());

            if cloze_num == target_ord {
                if !is_answer {
                    // Question view: occlude with hint or ellipsis
                    if let Some(h) = hint {
                        format!(r#"<span class="cloze cloze-hidden">[{}]</span>"#, h)
                    } else {
                        r#"<span class="cloze cloze-hidden">[...]</span>"#.to_string()
                    }
                } else {
                    // Answer view: show highlighted answer
                    format!(r#"<span class="cloze cloze-revealed">{}</span>"#, answer)
                }
            } else {
                // Not the target cloze: show regular text
                answer.to_string()
            }
        }).to_string()
    }

    /// Process {{#Field}}...{{/Field}} and {{^Field}}...{{/Field}} without regex backreferences
    fn process_conditionals(mut template: String, fields: &HashMap<String, String>) -> String {
        for (f_name, f_val) in fields {
            let is_empty = f_val.trim().is_empty();
            let open_tag = format!("{{{{#{}}}}}", f_name);
            let close_tag = format!("{{{{/{}}}}}", f_name);

            while let Some(start) = template.find(&open_tag) {
                if let Some(end) = template[start..].find(&close_tag) {
                    let close_start = start + end;
                    let close_end = close_start + close_tag.len();
                    let inner_start = start + open_tag.len();
                    if is_empty {
                        template.replace_range(start..close_end, "");
                    } else {
                        let inner = template[inner_start..close_start].to_string();
                        template.replace_range(start..close_end, &inner);
                    }
                } else {
                    break;
                }
            }

            let inv_open_tag = format!("{{{{^{}}}}}", f_name);
            while let Some(start) = template.find(&inv_open_tag) {
                if let Some(end) = template[start..].find(&close_tag) {
                    let close_start = start + end;
                    let close_end = close_start + close_tag.len();
                    let inner_start = start + inv_open_tag.len();
                    if !is_empty {
                        template.replace_range(start..close_end, "");
                    } else {
                        let inner = template[inner_start..close_start].to_string();
                        template.replace_range(start..close_end, &inner);
                    }
                } else {
                    break;
                }
            }
        }
        template
    }


    /// Extract list of unique decks from a slice of Cards
    pub fn extract_decks(cards: &[Card]) -> Vec<AnkiDeck> {
        let mut decks_map: HashMap<String, (usize, usize)> = HashMap::new(); // (total, due)

        for card in cards {
            let deck_name = card.deck_name.clone().unwrap_or_else(|| card.category.clone());
            let entry = decks_map.entry(deck_name).or_insert((0, 0));
            entry.0 += 1;
            if crate::spaced_repetition::SpacedRepetition::is_card_due(card) {
                entry.1 += 1;
            }
        }

        let mut result = Vec::new();
        for (name, (count, due)) in decks_map {
            result.push(AnkiDeck {
                id: format!("deck-{}", name.replace(' ', "-")),
                name: name.clone(),
                description: format!("رزمة {} تضم {} مسألة", name, count),
                card_count: count,
                due_count: due,
            });
        }

        result.sort_by(|a, b| a.name.cmp(&b.name));
        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn test_import_sample_apkg() {
        let apkg = PathBuf::from("../data/sample_hadith_cloze.apkg");
        let media_dir = std::env::temp_dir().join("zad_media_test");
        let (cards, result) = AnkiService::import_apkg(&apkg, &media_dir).expect("Import failed");
        assert_eq!(result.cards_imported, 9);
        assert_eq!(result.notes_imported, 4);
        assert_eq!(cards[0].card_type, "cloze");
        println!("Successfully imported {} cloze cards from sample apkg!", cards.len());
    }
}

