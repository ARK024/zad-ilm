/**
 * Zad Al-Ilm - Anki Decks & Templates Manager
 */

const DecksManager = (() => {
  let allDecks = [];
  let isImporting = false;

  const init = async () => {
    await loadDecks();
    setupDropZone();
  };

  const loadDecks = async () => {
    const container = document.getElementById('decks-grid');
    if (!container) return;

    try {
      allDecks = await ZadBridge.getDecks();
    } catch (e) {
      console.error('Failed to load decks:', e);
      allDecks = [];
    }

    renderDecks();
  };

  const renderDecks = () => {
    const container = document.getElementById('decks-grid');
    if (!container) return;

    if (allDecks.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; text-align:center; padding: 48px; background: var(--bg-surface); border-radius: var(--radius-lg); border: 1px dashed var(--border-color);">
          <div style="font-size: 40px; margin-bottom: 12px;">🗂️</div>
          <h3 style="color: var(--text-gold); margin-bottom: 8px;">لا توجد رزم أنكي مخصصة بعد</h3>
          <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 20px;">
            يمكنك استيراد أي ملف رزمة أنكي (<strong>.apkg</strong>) مباشرة عبر السحب والإفلات أو زر الاستيراد أدناه.
          </p>
          <button class="action-btn btn-primary" style="margin: 0 auto;" onclick="DecksManager.triggerFileInput()">
            <span>📥</span>
            <span>استيراد رزمة أنكي الآن</span>
          </button>
        </div>
      `;
      return;
    }

    container.innerHTML = allDecks.map(deck => {
      const hasDue = deck.due_count > 0;
      return `
        <div class="deck-card ${hasDue ? 'has-due' : ''}">
          <div class="deck-card-header">
            <span class="deck-icon">🗃️</span>
            <div class="deck-meta">
              <h4 class="deck-name">${escapeHtml(deck.name)}</h4>
              <span class="deck-desc">${escapeHtml(deck.description || '')}</span>
            </div>
          </div>

          <div class="deck-counts-row">
            <div class="deck-count-pill total">
              <span class="count-label">إجمالي البطاقات:</span>
              <strong class="count-val">${deck.card_count}</strong>
            </div>
            <div class="deck-count-pill due ${hasDue ? 'highlight' : ''}">
              <span class="count-label">مستحق اليوم:</span>
              <strong class="count-val">${deck.due_count}</strong>
            </div>
          </div>

          <div class="deck-actions-row">
            <button class="action-btn btn-primary btn-sm" onclick="DecksManager.studyDeck('${escapeAttr(deck.name)}')">
              <span>🎴</span>
              <span>دراسة واستذكار</span>
            </button>
            <button class="action-btn btn-gold btn-sm" onclick="DecksManager.quizDeck('${escapeAttr(deck.name)}')">
              <span>❓</span>
              <span>اختبار</span>
            </button>
          </div>
        </div>
      `;
    }).join('');
  };

  const studyDeck = (deckName) => {
    if (window.App) {
      window.App.switchView('study');
      window.StudySession.init(deckName);
    }
  };

  const quizDeck = (deckName) => {
    if (window.App) {
      window.App.switchView('quiz');
      window.QuizSession.init(deckName);
    }
  };

  const triggerFileInput = () => {
    const input = document.getElementById('anki-file-input');
    if (input) input.click();
  };

  const handleFileSelect = async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    await processApkgFile(file);
    event.target.value = '';
  };

  const setupDropZone = () => {
    const dropZone = document.getElementById('anki-drop-zone');
    if (!dropZone) return;

    ['dragenter', 'dragover'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('drag-active');
      }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('drag-active');
      }, false);
    });

    dropZone.addEventListener('drop', async (e) => {
      const dt = e.dataTransfer;
      const file = dt.files && dt.files[0];
      if (file) {
        await processApkgFile(file);
      }
    });
  };

  const processApkgFile = async (file) => {
    if (!file.name.endsWith('.apkg') && !file.name.endsWith('.colpkg') && !file.name.endsWith('.zip')) {
      alert('يرجى اختيار ملف رزمة أنكي بصيغة (.apkg أو .colpkg)');
      return;
    }

    showLoading(true, `جارٍ استيراد رزمة "${file.name}" واستخراج القوالب والوسائط...`);

    try {
      const reader = new FileReader();
      reader.onload = async (e) => {
        const base64Data = e.target.result;
        try {
          const result = await ZadBridge.importAnkiPackageBase64(file.name, base64Data);
          showLoading(false);
          showSuccessModal(result);
          await loadDecks();
          if (window.App) window.App.refreshTopBar();
        } catch (err) {
          showLoading(false);
          alert('فشل استيراد رزمة أنكي: ' + err);
          console.error(err);
        }
      };
      reader.readAsDataURL(file);
    } catch (err) {
      showLoading(false);
      alert('حدث خطأ أثناء قراءة الملف: ' + err);
    }
  };

  const showLoading = (show, text = '') => {
    const overlay = document.getElementById('anki-import-loading');
    const textEl = document.getElementById('anki-loading-text');
    if (overlay) {
      overlay.style.display = show ? 'flex' : 'none';
      if (textEl && text) textEl.textContent = text;
    }
  };

  const showSuccessModal = (result) => {
    const modal = document.getElementById('anki-import-success-modal');
    if (!modal) {
      alert(`ما شاء الله! تم استيراد رزمة "${result.deck_name}" بنجاح!\n\n• عدد البطاقات: ${result.cards_imported}\n• الملاحظات: ${result.notes_imported}\n• ملفات الوسائط: ${result.media_imported}`);
      return;
    }

    document.getElementById('import-res-deck').textContent = result.deck_name;
    document.getElementById('import-res-cards').textContent = result.cards_imported;
    document.getElementById('import-res-notes').textContent = result.notes_imported;
    document.getElementById('import-res-media').textContent = result.media_imported;

    modal.classList.add('active');
  };

  const closeSuccessModal = () => {
    const modal = document.getElementById('anki-import-success-modal');
    if (modal) modal.classList.remove('active');
  };

  const escapeHtml = (text) => {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  };

  const escapeAttr = (text) => {
    if (!text) return '';
    return text.replace(/'/g, "\\'");
  };

  return {
    init,
    loadDecks,
    studyDeck,
    quizDeck,
    triggerFileInput,
    handleFileSelect,
    closeSuccessModal
  };
})();

window.DecksManager = DecksManager;
