use anyhow::Result;
use log::info;
use std::sync::Arc;
use parking_lot::Mutex;
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIcon, TrayIconBuilder, TrayIconEvent},
    AppHandle,
};

const ID_TITLE: &str = "tray.title";
const ID_OPEN_MAIN: &str = "tray.open_main";
const ID_TOGGLE_WIDGET: &str = "tray.toggle_widget";
const ID_DUE_INFO: &str = "tray.due_info";
const ID_QUIT: &str = "tray.quit";

pub struct AppTray {
    tray: Arc<Mutex<Option<TrayIcon<tauri::Wry>>>>,
}

impl AppTray {
    pub fn new() -> Self {
        Self {
            tray: Arc::new(Mutex::new(None)),
        }
    }

    pub fn init(&self, app: &AppHandle, due_count: usize) -> Result<()> {
        let menu = build_menu(app, due_count)?;

        let mut builder = TrayIconBuilder::new()
            .menu(&menu)
            .show_menu_on_left_click(false)
            .tooltip("زاد العلم — تعلم العلوم الشرعية بالتكرار المتباعد");

        if let Some(icon) = app.default_window_icon() {
            builder = builder.icon(icon.clone());
        }

        let tray_icon = builder
            .on_menu_event(|app, event| {
                match event.id().as_ref() {
                    ID_OPEN_MAIN => {
                        let _ = crate::windows::create_or_show_main_window(app);
                    }
                    ID_TOGGLE_WIDGET => {
                        let _ = crate::windows::toggle_widget_window(app);
                    }
                    ID_QUIT => {
                        app.exit(0);
                    }
                    _ => {}
                }
            })
            .on_tray_icon_event(|tray, event| {
                if let TrayIconEvent::Click {
                    button: MouseButton::Left,
                    button_state: MouseButtonState::Up,
                    ..
                } = event
                {
                    let app = tray.app_handle();
                    let _ = crate::windows::create_or_show_main_window(app);
                }
            })
            .build(app)?;

        *self.tray.lock() = Some(tray_icon);
        info!("Tray icon created successfully");
        Ok(())
    }

    pub fn update_due_count(&self, app: &AppHandle, due_count: usize) {
        if let Some(ref tray) = *self.tray.lock() {
            if let Ok(new_menu) = build_menu(app, due_count) {
                let _ = tray.set_menu(Some(new_menu));
                let tooltip = format!("زاد العلم (مستحق للمراجعة: {})", due_count);
                let _ = tray.set_tooltip(Some(tooltip));
            }
        }
    }
}

fn build_menu(app: &AppHandle, due_count: usize) -> Result<Menu<tauri::Wry>> {
    let title_item = MenuItem::with_id(app, ID_TITLE, "زاد العلم — رفيقك الشرعي", false, None::<&str>)?;
    let sep1 = PredefinedMenuItem::separator(app)?;

    let open_main = MenuItem::with_id(app, ID_OPEN_MAIN, "📖 فتح النافذة الرئيسية", true, None::<&str>)?;
    let toggle_widget = MenuItem::with_id(app, ID_TOGGLE_WIDGET, "⚡ مراجعة سريعة (الودجت)", true, None::<&str>)?;

    let due_text = format!("🎯 المستحق للمراجعة اليوم: {}", due_count);
    let due_info = MenuItem::with_id(app, ID_DUE_INFO, &due_text, false, None::<&str>)?;

    let sep2 = PredefinedMenuItem::separator(app)?;
    let quit = MenuItem::with_id(app, ID_QUIT, "❌ إغلاق البرنامج", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[
        &title_item,
        &sep1,
        &open_main,
        &toggle_widget,
        &due_info,
        &sep2,
        &quit,
    ])?;

    Ok(menu)
}
