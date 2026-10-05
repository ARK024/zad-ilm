/**
 * Zad Al-Ilm - Deck Browser & Card Management
 */

const DeckBrowser = (() => {
  let allCards = [];
  let filteredCards = [];
  let editingCardId = null;

  const init = async () => {
    allCards = await ZadBridge.getCards();
    applyFilter();
    setupEventListeners();
  };

  const normalizeArabic = (text) => {
    if (!text) return '';
    return text
      .replace(/[\u064B-\u065F\u0670]/g, '') // Remove tashkeel
      .replace(/[إأآا]/g, 'ا')
      .replace(/ى/g, 'ي')
      .replace(/ة/g, 'ه')
      .toLowerCase()
      .trim();
  };

  const applyFilter = () => {
    const searchVal = normalizeArabic(document.getElementById('browser-search-input')?.value || '');
    const catVal = document.getElementById('browser-category-filter')?.value || 'all';
    const stateVal = document.getElementById('browser-state-filter')?.value || 'all';

    const now = new Date();

    filteredCards = allCards.filter(card => {
      // Category
      if (catVal !== 'all' && card.category !== catVal) return false;

      // State
      if (stateVal === 'due') {
        const isDue = card.state === 'new' || new Date(card.due_date) <= now;
        if (!isDue) return false;
      } else if (stateVal !== 'all' && card.state !== stateVal) {
        return false;
      }

      // Search Query
      if (searchVal) {
        const qNorm = normalizeArabic(card.question);
        const aNorm = normalizeArabic(card.answer);
        const tNorm = normalizeArabic(card.topic);
        if (!qNorm.includes(searchVal) && !aNorm.includes(searchVal) && !tNorm.includes(searchVal)) {
          return false;
        }
      }

      return true;
    });

    renderCardsList();
  };

  const renderCardsList = () => {
    const container = document.getElementById('browser-cards-list');
    const countEl = document.getElementById('browser-count-text');
    if (!container) return;

    if (countEl) {
      countEl.textContent = `عرض ${filteredCards.length} من إجمالي ${allCards.length} مسألة`;
    }

    if (filteredCards.length === 0) {
      container.innerHTML = `
        <div style="text-align:center; padding:40px; color:var(--text-muted);">
          <div style="font-size:32px; margin-bottom:8px;">🔍</div>
          <div>لم يتم العثور على أي مسائل تطابق البحث.</div>
        </div>
      `;
      return;
    }

    container.innerHTML = filteredCards.map(card => {
      const stateBadge = card.state === 'mastered' 
        ? '<span class="tag-badge" style="color:#34d399; border-color:#34d399;">متقنة</span>'
        : card.state === 'learning'
        ? '<span class="tag-badge" style="color:#fbbf24; border-color:#fbbf24;">قيد التعلم</span>'
        : '<span class="tag-badge" style="color:#60a5fa; border-color:#60a5fa;">جديدة</span>';

      return `
        <div class="browser-card-row">
          <div class="row-info">
            <div class="row-badges">
              <span class="tag-badge tag-category">${escapeHtml(card.category)}</span>
              <span class="tag-badge tag-topic">${escapeHtml(card.topic || '')}</span>
              ${stateBadge}
            </div>
            <div class="row-question">${escapeHtml(card.question)}</div>
            <div class="row-answer">${escapeHtml(card.answer || '')}</div>
          </div>
          <div class="row-actions">
            <button class="icon-btn" title="تعديل" onclick="DeckBrowser.openEditModal('${card.id}')">✏️</button>
            <button class="icon-btn danger" title="حذف" onclick="DeckBrowser.deleteCard('${card.id}')">🗑️</button>
          </div>
        </div>
      `;
    }).join('');
  };

  const setupEventListeners = () => {
    const searchInput = document.getElementById('browser-search-input');
    const catFilter = document.getElementById('browser-category-filter');
    const stateFilter = document.getElementById('browser-state-filter');

    if (searchInput) searchInput.addEventListener('input', applyFilter);
    if (catFilter) catFilter.addEventListener('change', applyFilter);
    if (stateFilter) stateFilter.addEventListener('change', applyFilter);
  };

  const openAddModal = () => {
    editingCardId = null;
    document.getElementById('modal-card-title').textContent = 'إضافة مسألة / بطاقة جديدة';
    document.getElementById('form-card-category').value = 'العقيدة والتوحيد';
    document.getElementById('form-card-topic').value = '';
    document.getElementById('form-card-type').value = 'flashcard';
    document.getElementById('form-card-question').value = '';
    document.getElementById('form-card-answer').value = '';
    document.getElementById('form-card-explanation').value = '';
    document.getElementById('form-card-options').value = '';
    document.getElementById('form-card-correct-idx').value = '0';

    toggleOptionsField();
    document.getElementById('card-edit-modal').classList.add('active');
  };

  const openEditModal = (cardId) => {
    const card = allCards.find(c => c.id === cardId);
    if (!card) return;

    editingCardId = cardId;
    document.getElementById('modal-card-title').textContent = 'تعديل المسألة';
    document.getElementById('form-card-category').value = card.category;
    document.getElementById('form-card-topic').value = card.topic || '';
    document.getElementById('form-card-type').value = card.type || 'flashcard';
    document.getElementById('form-card-question').value = card.question;
    document.getElementById('form-card-answer').value = card.answer;
    document.getElementById('form-card-explanation').value = card.explanation || '';
    document.getElementById('form-card-options').value = (card.options || []).join('\n');
    document.getElementById('form-card-correct-idx').value = card.correct_index >= 0 ? card.correct_index : 0;

    toggleOptionsField();
    document.getElementById('card-edit-modal').classList.add('active');
  };

  const closeModal = () => {
    document.getElementById('card-edit-modal').classList.remove('active');
  };

  const toggleOptionsField = () => {
    const type = document.getElementById('form-card-type').value;
    const optGroup = document.getElementById('form-quiz-options-group');
    if (optGroup) {
      optGroup.style.display = type === 'quiz' ? 'block' : 'none';
    }
  };

  const saveModalCard = async () => {
    const category = document.getElementById('form-card-category').value;
    const topic = document.getElementById('form-card-topic').value.trim();
    const type = document.getElementById('form-card-type').value;
    const question = document.getElementById('form-card-question').value.trim();
    const answer = document.getElementById('form-card-answer').value.trim();
    const explanation = document.getElementById('form-card-explanation').value.trim();

    if (!question || !answer) {
      alert('يرجى كتابة نص السؤال والإجابة.');
      return;
    }

    let options = [];
    let correct_index = -1;

    if (type === 'quiz') {
      const optRaw = document.getElementById('form-card-options').value.trim();
      options = optRaw.split('\n').map(o => o.trim()).filter(o => o.length > 0);
      correct_index = parseInt(document.getElementById('form-card-correct-idx').value, 10) || 0;
    }

    if (editingCardId) {
      const card = allCards.find(c => c.id === editingCardId);
      if (card) {
        card.category = category;
        card.topic = topic;
        card.type = type;
        card.question = question;
        card.answer = answer;
        card.explanation = explanation;
        card.options = options;
        card.correct_index = correct_index;
        await ZadBridge.updateCard(card);
      }
    } else {
      const newCard = {
        category,
        topic,
        type,
        question,
        answer,
        explanation,
        options,
        correct_index,
        difficulty: 'مبتدئ'
      };
      await ZadBridge.addCard(newCard);
    }

    closeModal();
    allCards = await ZadBridge.getCards();
    applyFilter();
    if (window.App) window.App.refreshTopBar();
  };

  const deleteCard = async (cardId) => {
    if (!confirm('هل أنت متأكد من حذف هذه المسألة؟')) return;
    try {
      await ZadBridge.deleteCard(cardId);
      allCards = allCards.filter(c => c.id !== cardId);
      applyFilter();
      if (window.App) window.App.refreshTopBar();
    } catch (err) {
      console.error('Delete error:', err);
    }
  };

  const exportData = async () => {
    try {
      const jsonStr = await ZadBridge.exportData();
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `zad_al_ilm_cards_${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('فشل تصدير البيانات: ' + err);
    }
  };

  const importData = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async (ev) => {
        try {
          const content = ev.target.result;
          const count = await ZadBridge.importData(content);
          alert(`تم استيراد ${count} مسألة بنجاح!`);
          allCards = await ZadBridge.getCards();
          applyFilter();
          if (window.App) window.App.refreshTopBar();
        } catch (err) {
          alert('خطأ أثناء قراءة ملف الاستيراد: ' + err);
        }
      };
      reader.readAsText(file);
    };
    input.click();
  };

  const escapeHtml = (text) => {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  };

  return {
    init,
    openAddModal,
    openEditModal,
    closeModal,
    toggleOptionsField,
    saveModalCard,
    deleteCard,
    exportData,
    importData
  };
})();

window.DeckBrowser = DeckBrowser;
