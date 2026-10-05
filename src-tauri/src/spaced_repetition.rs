use crate::models::{Card, ReviewRecord};
use chrono::{Duration, Utc};

pub struct SpacedRepetition;

impl SpacedRepetition {
    pub fn process_review(mut card: Card, rating: u8) -> (Card, ReviewRecord) {
        let now = Utc::now();
        let old_interval = card.interval;
        let old_ease = card.ease_factor;
        let was_correct = rating >= 3;

        card.total_reviews += 1;
        card.last_reviewed = Some(now.to_rfc3339());

        match rating {
            1 => {
                // Again: Forgotten or incorrect
                card.lapses += 1;
                card.repetitions = 0;
                card.interval = 1; // Due tomorrow (or 0 for immediate relearning)
                card.ease_factor = (card.ease_factor - 0.20).max(1.30);
                card.state = "learning".to_string();
                card.due_date = (now + Duration::days(1)).to_rfc3339();
            }
            2 => {
                // Hard: Remembered with great effort
                card.ease_factor = (card.ease_factor - 0.15).max(1.30);
                card.interval = if card.interval == 0 {
                    1
                } else {
                    ((card.interval as f32 * 1.2).round() as u32).max(card.interval + 1)
                };
                card.repetitions += 1;
                card.state = if card.interval >= 21 {
                    "mastered".to_string()
                } else {
                    "review".to_string()
                };
                card.due_date = (now + Duration::days(card.interval as i64)).to_rfc3339();
            }
            3 => {
                // Good: Remembered successfully
                if card.repetitions == 0 {
                    card.interval = 1;
                } else if card.repetitions == 1 {
                    card.interval = 3;
                } else {
                    card.interval = ((card.interval as f32 * card.ease_factor).round() as u32).max(card.interval + 1);
                }
                card.repetitions += 1;
                card.state = if card.interval >= 21 {
                    "mastered".to_string()
                } else {
                    "review".to_string()
                };
                card.due_date = (now + Duration::days(card.interval as i64)).to_rfc3339();
            }
            4 => {
                // Easy: Very easy recall
                card.ease_factor = (card.ease_factor + 0.15).min(3.50);
                if card.repetitions == 0 {
                    card.interval = 3;
                } else if card.repetitions == 1 {
                    card.interval = 6;
                } else {
                    card.interval = ((card.interval as f32 * card.ease_factor * 1.3).round() as u32).max(card.interval + 2);
                }
                card.repetitions += 1;
                card.state = if card.interval >= 21 {
                    "mastered".to_string()
                } else {
                    "review".to_string()
                };
                card.due_date = (now + Duration::days(card.interval as i64)).to_rfc3339();
            }
            _ => {
                // Default fallback
            }
        }

        let record = ReviewRecord {
            card_id: card.id.clone(),
            timestamp: now.to_rfc3339(),
            rating,
            old_interval,
            new_interval: card.interval,
            old_ease,
            new_ease: card.ease_factor,
            was_correct,
        };

        (card, record)
    }

    pub fn is_card_due(card: &Card) -> bool {
        if card.state == "new" {
            return true;
        }
        if let Ok(due) = chrono::DateTime::parse_from_rfc3339(&card.due_date) {
            let now = Utc::now();
            due <= now
        } else {
            true
        }
    }
}
