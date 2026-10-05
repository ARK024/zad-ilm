use crate::models::{AppSettings, Card, ReviewRecord};
use anyhow::Result;
use log::{info, warn};
use std::fs;
use std::path::{Path, PathBuf};

const DEFAULT_CARDS_JSON: &str = include_str!("../../data/islamic_sciences_cards.json");
const DEFAULT_SETTINGS_JSON: &str = include_str!("../../data/default_settings.json");

pub struct StorageManager {
    config_dir: PathBuf,
}

impl StorageManager {
    pub fn new() -> Self {
        let config_dir = dirs_or_fallback();
        if let Err(e) = fs::create_dir_all(&config_dir) {
            warn!("Failed to create config dir {:?}: {}", config_dir, e);
        }
        Self { config_dir }
    }

    pub fn get_config_dir(&self) -> &Path {
        &self.config_dir
    }

    fn cards_path(&self) -> PathBuf {
        self.config_dir.join("cards.json")
    }

    fn settings_path(&self) -> PathBuf {
        self.config_dir.join("settings.json")
    }

    fn history_path(&self) -> PathBuf {
        self.config_dir.join("review_history.json")
    }

    pub fn load_cards(&self) -> Vec<Card> {
        let path = self.cards_path();
        if path.exists() {
            match fs::read_to_string(&path) {
                Ok(content) => match serde_json::from_str::<Vec<Card>>(&content) {
                    Ok(cards) => {
                        info!("Loaded {} cards from {:?}", cards.len(), path);
                        return cards;
                    }
                    Err(e) => warn!("Failed to parse cards at {:?}: {}", path, e),
                },
                Err(e) => warn!("Failed to read cards at {:?}: {}", path, e),
            }
        }

        // Fallback to bundled default cards
        info!("Initializing cards from default embedded database...");
        let default_cards: Vec<Card> = serde_json::from_str(DEFAULT_CARDS_JSON).unwrap_or_default();
        let _ = self.save_cards(&default_cards);
        default_cards
    }

    pub fn save_cards(&self, cards: &[Card]) -> Result<()> {
        let path = self.cards_path();
        let content = serde_json::to_string_pretty(cards)?;
        let tmp_path = self.config_dir.join("cards.json.tmp");
        fs::write(&tmp_path, content)?;
        fs::rename(tmp_path, path)?;
        Ok(())
    }

    pub fn load_settings(&self) -> AppSettings {
        let path = self.settings_path();
        if path.exists() {
            if let Ok(content) = fs::read_to_string(&path) {
                if let Ok(settings) = serde_json::from_str::<AppSettings>(&content) {
                    return settings;
                }
            }
        }

        // Fallback to default
        let default_settings: AppSettings = serde_json::from_str(DEFAULT_SETTINGS_JSON).unwrap_or_default();
        let _ = self.save_settings(&default_settings);
        default_settings
    }

    pub fn save_settings(&self, settings: &AppSettings) -> Result<()> {
        let path = self.settings_path();
        let content = serde_json::to_string_pretty(settings)?;
        fs::write(path, content)?;
        Ok(())
    }

    pub fn append_review_history(&self, record: &ReviewRecord) -> Result<()> {
        let path = self.history_path();
        let mut history: Vec<ReviewRecord> = if path.exists() {
            fs::read_to_string(&path)
                .ok()
                .and_then(|c| serde_json::from_str(&c).ok())
                .unwrap_or_default()
        } else {
            Vec::new()
        };

        history.push(record.clone());
        // Cap history to last 5,000 entries to maintain high performance
        if history.len() > 5000 {
            history.drain(0..(history.len() - 5000));
        }

        let content = serde_json::to_string(&history)?;
        fs::write(path, content)?;
        Ok(())
    }

    pub fn get_today_reviews_count(&self) -> usize {
        let path = self.history_path();
        if !path.exists() {
            return 0;
        }

        let today = chrono::Local::now().format("%Y-%m-%d").to_string();
        if let Ok(content) = fs::read_to_string(&path) {
            if let Ok(history) = serde_json::from_str::<Vec<ReviewRecord>>(&content) {
                return history
                    .iter()
                    .filter(|r| r.timestamp.starts_with(&today))
                    .count();
            }
        }
        0
    }
}

fn dirs_or_fallback() -> PathBuf {
    #[cfg(target_os = "windows")]
    {
        if let Ok(appdata) = std::env::var("APPDATA") {
            return PathBuf::from(appdata).join("zad-al-ilm");
        }
    }

    #[cfg(target_os = "macos")]
    {
        if let Ok(home) = std::env::var("HOME") {
            return PathBuf::from(home)
                .join("Library")
                .join("Application Support")
                .join("zad-al-ilm");
        }
    }

    if let Ok(home) = std::env::var("HOME") {
        PathBuf::from(home).join(".config").join("zad-al-ilm")
    } else {
        PathBuf::from(".zad-al-ilm")
    }
}
