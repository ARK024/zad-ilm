pub mod anki;
pub mod ipc;
pub mod models;
pub mod spaced_repetition;
pub mod storage;
pub mod tray;
pub mod windows;

use env_logger::Env;
use log::{error, info};
use std::sync::Arc;
use tauri::AppHandle;

pub fn run() {
    env_logger::Builder::from_env(Env::default().default_filter_or("info")).init();
    info!("Starting Zad Al-Ilm application...");

    let tray = Arc::new(tray::AppTray::new());
    let state = Arc::new(ipc::AppState::new(tray.clone()));

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(state.clone())
        .setup({
            let tray = tray.clone();
            let state = state.clone();
            move |app| {
                let handle = app.handle().clone();

                // 1. Initialize Tray
                let due_count = state.count_due();
                if let Err(e) = tray.init(&handle, due_count) {
                    error!("Failed to initialize tray icon: {}", e);
                }

                // 2. Open Main Study Window
                if let Err(e) = windows::create_or_show_main_window(&handle) {
                    error!("Failed to open main study window: {}", e);
                }

                // 3. Start background periodic widget checker
                let handle_clone = handle.clone();
                let state_clone = state.clone();
                tauri::async_runtime::spawn(async move {
                    background_widget_scheduler(handle_clone, state_clone).await;
                });

                Ok(())
            }
        })
        .invoke_handler(tauri::generate_handler![
            ipc::get_cards,
            ipc::get_due_cards,
            ipc::get_random_card,
            ipc::review_card,
            ipc::check_quiz_answer,
            ipc::get_stats,
            ipc::get_settings,
            ipc::save_settings,
            ipc::add_card,
            ipc::update_card,
            ipc::delete_card,
            ipc::export_data,
            ipc::import_data,
            ipc::show_widget,
            ipc::hide_widget,
            ipc::show_main_window,
            ipc::close_app,
            ipc::get_decks,
            ipc::get_cards_by_deck,
            ipc::import_anki_package,
            ipc::import_anki_package_base64,
            ipc::render_anki_template,
        ])
        .run(tauri::generate_context!())
        .expect("Error while running Zad Al-Ilm");
}

async fn background_widget_scheduler(app: AppHandle, state: Arc<ipc::AppState>) {
    use tokio::time::{sleep, Duration};

    // Wait 2 minutes after startup before checking periodic reminders
    sleep(Duration::from_secs(120)).await;

    loop {
        let (enabled, interval_mins) = {
            let settings = state.settings.read();
            (
                settings.widget_enabled,
                settings.auto_widget_interval_minutes.max(5),
            )
        };

        if enabled {
            let due_count = state.count_due();
            if due_count > 0 {
                info!("Auto-triggering review widget for {} due cards", due_count);
                let _ = windows::create_or_show_widget_window(&app);
            }
        }

        sleep(Duration::from_secs((interval_mins as u64) * 60)).await;
    }
}
