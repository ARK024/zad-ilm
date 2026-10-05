use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Card {
    pub id: String,
    pub category: String,
    pub topic: String,
    #[serde(rename = "type")]
    pub card_type: String, // "quiz" | "flashcard" | "cloze"
    pub question: String,
    #[serde(default)]
    pub options: Vec<String>,
    #[serde(default = "default_correct_index")]
    pub correct_index: i32,
    pub answer: String,
    #[serde(default)]
    pub explanation: String,
    #[serde(default = "default_difficulty")]
    pub difficulty: String, // "مبتدئ" | "متوسط" | "متقدم"

    // Spaced repetition fields (SM-2)
    #[serde(default)]
    pub repetitions: u32,
    #[serde(default)]
    pub interval: u32, // in days
    #[serde(default = "default_ease_factor")]
    pub ease_factor: f32,
    #[serde(default = "default_due_date")]
    pub due_date: String, // ISO timestamp
    #[serde(default = "default_state")]
    pub state: String, // "new" | "learning" | "review" | "mastered"
    #[serde(default)]
    pub total_reviews: u32,
    #[serde(default)]
    pub lapses: u32,
    #[serde(default)]
    pub last_reviewed: Option<String>,

    // Anki integration & template fields
    #[serde(default)]
    pub deck_id: Option<String>,
    #[serde(default)]
    pub deck_name: Option<String>,
    #[serde(default)]
    pub note_id: Option<String>,
    #[serde(default)]
    pub note_type: Option<String>,
    #[serde(default)]
    pub template_name: Option<String>,
    #[serde(default)]
    pub fields: Option<HashMap<String, String>>,
    #[serde(default)]
    pub qfmt: Option<String>, // Question HTML template
    #[serde(default)]
    pub afmt: Option<String>, // Answer HTML template
    #[serde(default)]
    pub css: Option<String>,  // Template CSS
    #[serde(default)]
    pub cloze_ord: Option<u32>, // Cloze index (1 for c1, 2 for c2, ...)
    #[serde(default)]
    pub media_files: Option<Vec<String>>,
}

fn default_correct_index() -> i32 {
    -1
}

fn default_difficulty() -> String {
    "مبتدئ".to_string()
}

fn default_ease_factor() -> f32 {
    2.5
}

fn default_due_date() -> String {
    chrono::Utc::now().to_rfc3339()
}

fn default_state() -> String {
    "new".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnkiDeck {
    pub id: String,
    pub name: String,
    pub description: String,
    pub card_count: usize,
    pub due_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NoteType {
    pub id: String,
    pub name: String,
    pub fields: Vec<String>,
    pub templates: Vec<CardTemplate>,
    pub css: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CardTemplate {
    pub name: String,
    pub qfmt: String,
    pub afmt: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnkiImportResult {
    pub deck_name: String,
    pub cards_imported: usize,
    pub notes_imported: usize,
    pub media_imported: usize,
    pub decks_found: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReviewRecord {
    pub card_id: String,
    pub timestamp: String,
    pub rating: u8, // 1: Again, 2: Hard, 3: Good, 4: Easy
    pub old_interval: u32,
    pub new_interval: u32,
    pub old_ease: f32,
    pub new_ease: f32,
    pub was_correct: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppSettings {
    pub daily_goal: u32,
    pub auto_widget_interval_minutes: u32,
    pub widget_enabled: bool,
    pub widget_always_on_top: bool,
    pub theme: String,
    pub sound_enabled: bool,
    pub streak_count: u32,
    pub last_study_date: String,
    pub total_reviewed_all_time: u32,
    pub active_categories: Vec<String>,
    pub active_deck: Option<String>,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            daily_goal: 15,
            auto_widget_interval_minutes: 30,
            widget_enabled: true,
            widget_always_on_top: true,
            theme: "emerald-dark".to_string(),
            sound_enabled: true,
            streak_count: 1,
            last_study_date: chrono::Local::now().format("%Y-%m-%d").to_string(),
            total_reviewed_all_time: 0,
            active_categories: vec![
                "العقيدة والتوحيد".to_string(),
                "فقه العبادات".to_string(),
                "الحديث ومصطلحه".to_string(),
                "علوم القرآن والتفسير".to_string(),
                "السيرة النبوية والآداب".to_string(),
                "أصول الفقه".to_string(),
                "اللغة العربية والنحو".to_string(),
            ],
            active_deck: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StudyStats {
    pub total_cards: usize,
    pub new_cards: usize,
    pub learning_cards: usize,
    pub review_due: usize,
    pub mastered_cards: usize,
    pub reviewed_today: usize,
    pub daily_goal: u32,
    pub streak_count: u32,
    pub categories_counts: HashMap<String, usize>,
    pub decks_counts: HashMap<String, usize>,
}
