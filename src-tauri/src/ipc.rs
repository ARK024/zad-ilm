use crate::anki::AnkiService;
use crate::models::{AnkiDeck, AnkiImportResult, AppSettings, Card, StudyStats};
use crate::spaced_repetition::SpacedRepetition;
use crate::storage::StorageManager;
use crate::tray::AppTray;
use parking_lot::RwLock;
use serde_json::json;
use std::collections::HashMap;
use std::sync::Arc;
use tauri::{AppHandle, State};

pub struct AppState {
    pub storage: StorageManager,
    pub cards: RwLock<Vec<Card>>,
    pub settings: RwLock<AppSettings>,
    pub tray: Arc<AppTray>,
}

impl AppState {
    pub fn new(tray: Arc<AppTray>) -> Self {
        let storage = StorageManager::new();
        let cards = storage.load_cards();
        let settings = storage.load_settings();
        Self {
            storage,
            cards: RwLock::new(cards),
            settings: RwLock::new(settings),
            tray,
        }
    }

    pub fn count_due(&self) -> usize {
        let cards = self.cards.read();
        cards.iter().filter(|c| SpacedRepetition::is_card_due(c)).count()
    }
}

#[tauri::command]
pub fn get_cards(state: State<'_, Arc<AppState>>) -> Vec<Card> {
    state.cards.read().clone()
}

#[tauri::command]
pub fn get_due_cards(state: State<'_, Arc<AppState>>) -> Vec<Card> {
    let cards = state.cards.read();
    cards
        .iter()
        .filter(|c| SpacedRepetition::is_card_due(c))
        .cloned()
        .collect()
}

#[tauri::command]
pub fn get_random_card(
    category: Option<String>,
    only_due: Option<bool>,
    state: State<'_, Arc<AppState>>,
) -> Option<Card> {
    use rand::seq::SliceRandom;
    let cards = state.cards.read();
    let mut filtered: Vec<&Card> = cards.iter().collect();

    if let Some(cat) = category {
        if !cat.is_empty() && cat != "all" && cat != "الكل" {
            filtered.retain(|c| c.category == cat);
        }
    }

    if only_due.unwrap_or(false) {
        filtered.retain(|c| SpacedRepetition::is_card_due(c));
    }

    let mut rng = rand::thread_rng();
    filtered.choose(&mut rng).map(|&c| c.clone())
}

#[tauri::command]
pub fn review_card(
    card_id: String,
    rating: u8,
    app: AppHandle,
    state: State<'_, Arc<AppState>>,
) -> Result<Card, String> {
    let mut cards = state.cards.write();
    let idx = cards
        .iter()
        .position(|c| c.id == card_id)
        .ok_or_else(|| "Card not found".to_string())?;

    let old_card = cards[idx].clone();
    let (new_card, record) = SpacedRepetition::process_review(old_card, rating);
    cards[idx] = new_card.clone();

    // Persist card updates and review log
    let _ = state.storage.save_cards(&cards);
    let _ = state.storage.append_review_history(&record);

    // Update settings: total_reviewed_all_time & streak
    {
        let mut settings = state.settings.write();
        settings.total_reviewed_all_time += 1;
        let today = chrono::Local::now().format("%Y-%m-%d").to_string();
        if settings.last_study_date != today {
            // Check if yesterday or consecutive
            settings.streak_count += 1;
            settings.last_study_date = today;
        }
        let _ = state.storage.save_settings(&settings);
    }

    // Refresh tray due count
    let due_count = cards.iter().filter(|c| SpacedRepetition::is_card_due(c)).count();
    state.tray.update_due_count(&app, due_count);

    Ok(new_card)
}

#[tauri::command]
pub fn check_quiz_answer(
    card_id: String,
    selected_index: i32,
    app: AppHandle,
    state: State<'_, Arc<AppState>>,
) -> Result<serde_json::Value, String> {
    let cards = state.cards.read();
    let card = cards
        .iter()
        .find(|c| c.id == card_id)
        .cloned()
        .ok_or_else(|| "Card not found".to_string())?;
    drop(cards);

    let is_correct = card.correct_index == selected_index;
    let rating: u8 = if is_correct { 3 } else { 1 };

    let updated_card = review_card(card_id, rating, app, state)?;

    Ok(json!({
        "is_correct": is_correct,
        "correct_index": card.correct_index,
        "explanation": card.explanation,
        "answer": card.answer,
        "updated_card": updated_card
    }))
}

#[tauri::command]
pub fn get_stats(state: State<'_, Arc<AppState>>) -> StudyStats {
    let cards = state.cards.read();
    let settings = state.settings.read();

    let mut new_cards = 0;
    let mut learning_cards = 0;
    let mut review_due = 0;
    let mut mastered_cards = 0;
    let mut categories_counts = HashMap::new();

    for card in cards.iter() {
        *categories_counts.entry(card.category.clone()).or_insert(0) += 1;
        if card.state == "new" {
            new_cards += 1;
        } else if card.state == "learning" {
            learning_cards += 1;
        } else if card.state == "mastered" {
            mastered_cards += 1;
        }

        if SpacedRepetition::is_card_due(card) {
            review_due += 1;
        }
    }

    let mut decks_counts = HashMap::new();
    for card in cards.iter() {
        let deck_name = card.deck_name.clone().unwrap_or_else(|| card.category.clone());
        *decks_counts.entry(deck_name).or_insert(0) += 1;
    }

    let reviewed_today = state.storage.get_today_reviews_count();

    StudyStats {
        total_cards: cards.len(),
        new_cards,
        learning_cards,
        review_due,
        mastered_cards,
        reviewed_today,
        daily_goal: settings.daily_goal,
        streak_count: settings.streak_count,
        categories_counts,
        decks_counts,
    }
}

#[tauri::command]
pub fn get_settings(state: State<'_, Arc<AppState>>) -> AppSettings {
    state.settings.read().clone()
}

#[tauri::command]
pub fn save_settings(settings: AppSettings, state: State<'_, Arc<AppState>>) -> Result<(), String> {
    state.storage.save_settings(&settings).map_err(|e| e.to_string())?;
    *state.settings.write() = settings;
    Ok(())
}

#[tauri::command]
pub fn add_card(mut card: Card, state: State<'_, Arc<AppState>>) -> Result<Card, String> {
    if card.id.is_empty() {
        card.id = format!("custom-{}", uuid::Uuid::new_v4().to_string()[0..8].to_string());
    }
    if card.due_date.is_empty() {
        card.due_date = chrono::Utc::now().to_rfc3339();
    }
    if card.ease_factor <= 0.0 {
        card.ease_factor = 2.5;
    }
    card.state = "new".to_string();

    let mut cards = state.cards.write();
    cards.push(card.clone());
    state.storage.save_cards(&cards).map_err(|e| e.to_string())?;

    Ok(card)
}

#[tauri::command]
pub fn update_card(card: Card, state: State<'_, Arc<AppState>>) -> Result<(), String> {
    let mut cards = state.cards.write();
    if let Some(idx) = cards.iter().position(|c| c.id == card.id) {
        cards[idx] = card;
        state.storage.save_cards(&cards).map_err(|e| e.to_string())?;
        Ok(())
    } else {
        Err("Card not found".to_string())
    }
}

#[tauri::command]
pub fn delete_card(card_id: String, state: State<'_, Arc<AppState>>) -> Result<(), String> {
    let mut cards = state.cards.write();
    let initial_len = cards.len();
    cards.retain(|c| c.id != card_id);
    if cards.len() != initial_len {
        state.storage.save_cards(&cards).map_err(|e| e.to_string())?;
        Ok(())
    } else {
        Err("Card not found".to_string())
    }
}

#[tauri::command]
pub fn export_data(state: State<'_, Arc<AppState>>) -> Result<String, String> {
    let cards = state.cards.read();
    serde_json::to_string_pretty(&*cards).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn import_data(json_data: String, state: State<'_, Arc<AppState>>) -> Result<usize, String> {
    let imported_cards: Vec<Card> = serde_json::from_str(&json_data).map_err(|e| e.to_string())?;
    let count = imported_cards.len();

    let mut cards = state.cards.write();
    for imp in imported_cards {
        if let Some(idx) = cards.iter().position(|c| c.id == imp.id) {
            cards[idx] = imp;
        } else {
            cards.push(imp);
        }
    }

    state.storage.save_cards(&cards).map_err(|e| e.to_string())?;
    Ok(count)
}

#[tauri::command]
pub fn show_widget(app: AppHandle) -> Result<(), String> {
    crate::windows::create_or_show_widget_window(&app).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn hide_widget(app: AppHandle) {
    crate::windows::hide_widget_window(&app);
}

#[tauri::command]
pub fn show_main_window(app: AppHandle) -> Result<(), String> {
    crate::windows::create_or_show_main_window(&app).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn close_app(app: AppHandle) {
    app.exit(0);
}

#[tauri::command]
pub fn get_decks(state: State<'_, Arc<AppState>>) -> Vec<AnkiDeck> {
    let cards = state.cards.read();
    AnkiService::extract_decks(&cards)
}

#[tauri::command]
pub fn get_cards_by_deck(deck_name: String, state: State<'_, Arc<AppState>>) -> Vec<Card> {
    let cards = state.cards.read();
    cards
        .iter()
        .filter(|c| {
            if deck_name == "all" || deck_name == "الكل" {
                true
            } else if let Some(ref d) = c.deck_name {
                d == &deck_name || d.starts_with(&format!("{}::", deck_name))
            } else {
                c.category == deck_name
            }
        })
        .cloned()
        .collect()
}

#[tauri::command]
pub fn import_anki_package(
    file_path: String,
    app: AppHandle,
    state: State<'_, Arc<AppState>>,
) -> Result<AnkiImportResult, String> {
    let media_dir = state.storage.get_config_dir().join("media");
    let path = std::path::PathBuf::from(file_path);
    let (imported_cards, result) = AnkiService::import_apkg(&path, &media_dir).map_err(|e| e.to_string())?;

    let mut cards = state.cards.write();
    for imp in imported_cards {
        if let Some(idx) = cards.iter().position(|c| c.id == imp.id) {
            cards[idx] = imp;
        } else {
            cards.push(imp);
        }
    }

    state.storage.save_cards(&cards).map_err(|e| e.to_string())?;

    let due_count = cards.iter().filter(|c| SpacedRepetition::is_card_due(c)).count();
    state.tray.update_due_count(&app, due_count);

    Ok(result)
}

#[tauri::command]
pub fn import_anki_package_base64(
    file_name: String,
    base64_data: String,
    app: AppHandle,
    state: State<'_, Arc<AppState>>,
) -> Result<AnkiImportResult, String> {
    use std::io::Write;
    let data = match base64_data.split(',').last() {
        Some(d) => d,
        None => &base64_data,
    };

    use base64::Engine;
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(data.trim())
        .map_err(|e| format!("Base64 decode error: {}", e))?;

    let temp_file = std::env::temp_dir().join(format!("import_{}_{}", uuid::Uuid::new_v4(), file_name));
    let mut file = std::fs::File::create(&temp_file).map_err(|e| e.to_string())?;
    file.write_all(&bytes).map_err(|e| e.to_string())?;
    drop(file);

    let media_dir = state.storage.get_config_dir().join("media");
    let import_res = AnkiService::import_apkg(&temp_file, &media_dir);
    let _ = std::fs::remove_file(&temp_file);

    let (imported_cards, result) = import_res.map_err(|e| e.to_string())?;

    let mut cards = state.cards.write();
    for imp in imported_cards {
        if let Some(idx) = cards.iter().position(|c| c.id == imp.id) {
            cards[idx] = imp;
        } else {
            cards.push(imp);
        }
    }

    state.storage.save_cards(&cards).map_err(|e| e.to_string())?;
    let due_count = cards.iter().filter(|c| SpacedRepetition::is_card_due(c)).count();
    state.tray.update_due_count(&app, due_count);

    Ok(result)
}

#[tauri::command]
pub fn render_anki_template(
    template: String,
    fields: HashMap<String, String>,
    cloze_ord: Option<u32>,
    is_answer: bool,
    front_side: Option<String>,
) -> String {
    AnkiService::render_template(&template, &fields, cloze_ord, is_answer, front_side.as_deref())
}

