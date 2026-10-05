/**
 * Zad Al-Ilm - Main Application Controller
 */

const App = (() => {
  let currentView = 'dashboard';
  let statsData = null;

  const init = async () => {
    setupNavigation();
    await refreshTopBar();
    await loadDashboard();
    setupSettingsEvents();
  };

  const setupNavigation = () => {
    const navButtons = document.querySelectorAll('.nav-btn');
    navButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const viewId = btn.getAttribute('data-view');
        switchView(viewId);
      });
    });
  };

  const switchView = async (viewId) => {
    currentView = viewId;

    // Update active class on nav
    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-view') === viewId);
    });

    // Hide all views, show selected
    document.querySelectorAll('.content-section').forEach(sec => {
      sec.classList.remove('active');
    });

    const targetSection = document.getElementById(`view-${viewId}`);
    if (targetSection) targetSection.classList.add('active');

    // Title update
    const titles = {
      dashboard: 'الرئيسية والإحصائيات',
      decks: 'رزم أنكي وإدارة القوالب',
      study: 'جلسة الاستذكار (التكرار المتباعد)',
      quiz: 'بنك الأسئلة واختبارات الفهم',
      browser: 'مستعرض العلوم والبطاقات',
      settings: 'الإعدادات والنسخ الاحتياطي'
    };
    document.getElementById('top-bar-title').textContent = titles[viewId] || 'زاد العلم';

    // View specific initialization
    if (viewId === 'dashboard') {
      await loadDashboard();
    } else if (viewId === 'decks') {
      await window.DecksManager.init();
    } else if (viewId === 'study') {
      await window.StudySession.init('all');
    } else if (viewId === 'quiz') {
      await window.QuizSession.init('all');
    } else if (viewId === 'browser') {
      await window.DeckBrowser.init();
    } else if (viewId === 'settings') {
      await loadSettingsView();
    }

    await refreshTopBar();
  };

  const refreshTopBar = async () => {
    try {
      statsData = await ZadBridge.getStats();
      document.getElementById('top-streak-count').textContent = statsData.streak_count || 1;
      document.getElementById('top-due-count').textContent = statsData.review_due || 0;

      // Update badge in sidebar for study
      const studyBadge = document.getElementById('nav-study-badge');
      if (studyBadge) {
        studyBadge.textContent = statsData.review_due || 0;
        studyBadge.style.display = statsData.review_due > 0 ? 'inline-block' : 'none';
      }
    } catch (err) {
      console.warn('Failed to refresh stats in top bar:', err);
    }
  };

  const loadDashboard = async () => {
    await refreshTopBar();
    if (!statsData) return;

    // Metric cards
    document.getElementById('metric-due-val').textContent = statsData.review_due;
    document.getElementById('metric-today-val').textContent = `${statsData.reviewed_today} / ${statsData.daily_goal}`;
    document.getElementById('metric-mastered-val').textContent = statsData.mastered_cards;
    document.getElementById('metric-total-val').textContent = statsData.total_cards;

    // Render Categories breakdown chips
    const chipsContainer = document.getElementById('category-chips-list');
    if (chipsContainer && statsData.categories_counts) {
      chipsContainer.innerHTML = Object.entries(statsData.categories_counts).map(([cat, count]) => `
        <div class="category-chip" onclick="App.startCategoryStudy('${cat}')">
          <span class="category-chip-name">${cat}</span>
          <span class="category-chip-count">${count} مسألة</span>
        </div>
      `).join('');
    }
  };

  const startCategoryStudy = async (category) => {
    switchView('study');
    await window.StudySession.init(category);
  };

  const startCategoryQuiz = async (category) => {
    switchView('quiz');
    await window.QuizSession.init(category);
  };

  const openWidget = () => {
    ZadBridge.showWidget();
  };

  const loadSettingsView = async () => {
    try {
      const settings = await ZadBridge.getSettings();
      document.getElementById('setting-daily-goal').value = settings.daily_goal || 15;
      document.getElementById('setting-widget-interval').value = settings.auto_widget_interval_minutes || 30;
      document.getElementById('setting-widget-enabled').checked = settings.widget_enabled !== false;
      document.getElementById('setting-sound-enabled').checked = settings.sound_enabled !== false;
      document.getElementById('setting-total-reviews').textContent = settings.total_reviewed_all_time || 0;
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  };

  const setupSettingsEvents = () => {
    const saveBtn = document.getElementById('btn-save-settings');
    if (saveBtn) {
      saveBtn.addEventListener('click', async () => {
        const settings = await ZadBridge.getSettings();
        settings.daily_goal = parseInt(document.getElementById('setting-daily-goal').value, 10) || 15;
        settings.auto_widget_interval_minutes = parseInt(document.getElementById('setting-widget-interval').value, 10) || 30;
        settings.widget_enabled = document.getElementById('setting-widget-enabled').checked;
        settings.sound_enabled = document.getElementById('setting-sound-enabled').checked;

        await ZadBridge.saveSettings(settings);
        alert('تم حفظ الإعدادات بنجاح!');
        await refreshTopBar();
      });
    }
  };

  return {
    init,
    switchView,
    refreshTopBar,
    startCategoryStudy,
    startCategoryQuiz,
    openWidget
  };
})();

window.App = App;

document.addEventListener('DOMContentLoaded', () => {
  App.init();
});
