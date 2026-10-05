use anyhow::Result;
use log::info;
use tauri::{
    AppHandle, Manager, WebviewUrl, WebviewWindow,
    WebviewWindowBuilder,
};

pub const MAIN_LABEL: &str = "main";
pub const WIDGET_LABEL: &str = "widget";

pub fn create_or_show_main_window(app: &AppHandle) -> Result<WebviewWindow> {
    if let Some(w) = app.get_webview_window(MAIN_LABEL) {
        let _ = w.show();
        let _ = w.unminimize();
        let _ = w.set_focus();
        return Ok(w);
    }

    info!("Creating main window...");
    let builder = WebviewWindowBuilder::new(app, MAIN_LABEL, WebviewUrl::App("index.html".into()))
        .title("زاد العلم — منصة وتكرار متباعد للعلوم الشرعية")
        .inner_size(1140.0, 780.0)
        .min_inner_size(800.0, 600.0)
        .resizable(true)
        .center()
        .decorations(true);

    let window = builder.build()?;
    let _ = window.show();
    let _ = window.set_focus();
    Ok(window)
}

pub fn create_or_show_widget_window(app: &AppHandle) -> Result<WebviewWindow> {
    if let Some(w) = app.get_webview_window(WIDGET_LABEL) {
        let _ = w.show();
        let _ = w.unminimize();
        let _ = w.set_focus();
        return Ok(w);
    }

    info!("Creating desktop widget window...");
    let (x, y) = compute_widget_pos(app, 440.0, 520.0);

    let builder = WebviewWindowBuilder::new(app, WIDGET_LABEL, WebviewUrl::App("widget.html".into()))
        .title("زاد العلم — الودجت السريع")
        .inner_size(440.0, 520.0)
        .position(x, y)
        .resizable(false)
        .always_on_top(true)
        .decorations(false)
        .transparent(true)
        .skip_taskbar(true);

    let window = builder.build()?;
    let _ = window.show();
    Ok(window)
}

pub fn hide_widget_window(app: &AppHandle) {
    if let Some(w) = app.get_webview_window(WIDGET_LABEL) {
        let _ = w.hide();
    }
}

pub fn toggle_widget_window(app: &AppHandle) -> Result<()> {
    if let Some(w) = app.get_webview_window(WIDGET_LABEL) {
        if w.is_visible().unwrap_or(false) {
            let _ = w.hide();
            return Ok(());
        }
    }
    create_or_show_widget_window(app)?;
    Ok(())
}

fn compute_widget_pos(app: &AppHandle, w: f64, h: f64) -> (f64, f64) {
    if let Ok(Some(primary)) = app.primary_monitor() {
        let scale = primary.scale_factor();
        let size = primary.size();
        let sw = size.width as f64 / scale;
        let sh = size.height as f64 / scale;
        // Position at bottom-left for Arabic RTL desktop or bottom-right
        let x = sw - w - 24.0;
        let y = sh - h - 48.0;
        return (x.max(10.0), y.max(10.0));
    }
    (50.0, 50.0)
}
