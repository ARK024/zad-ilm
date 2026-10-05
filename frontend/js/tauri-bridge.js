/**
 * Zad Al-Ilm - Tauri Bridge & Data Service
 * Provides seamless bridge between UI and Tauri 2 Rust backend,
 * with fallback storage for web browser testing.
 */

const Bridge = (() => {
  const isTauri = () => {
    return typeof window !== 'undefined' && 
           window.__TAURI__ !== undefined && 
           window.__TAURI__.core !== undefined;
  };

  const invoke = async (cmd, args = {}) => {
    if (isTauri()) {
      try {
        return await window.__TAURI__.core.invoke(cmd, args);
      } catch (err) {
        console.error(`Tauri invoke error for ${cmd}:`, err);
        throw err;
      }
    } else {
      return webFallbackInvoke(cmd, args);
    }
  };

  // LocalStorage Web Fallback for testing in standard browser
  const STORAGE_KEY_CARDS = 'zad_ilm_cards';
  const STORAGE_KEY_SETTINGS = 'zad_ilm_settings';
  const STORAGE_KEY_REVIEWS = 'zad_ilm_reviews';

  const loadWebCards = async () => {
    const saved = localStorage.getItem(STORAGE_KEY_CARDS);
    if (saved) {
      try { return JSON.parse(saved); } catch(e) {}
    }
    // Fetch default cards
    try {
      const resp = await fetch('../data/islamic_sciences_cards.json');
      if (resp.ok) {
        const cards = await resp.json();
        localStorage.setItem(STORAGE_KEY_CARDS, JSON.stringify(cards));
        return cards;
      }
    } catch(e) {
      console.warn('Could not fetch default cards json:', e);
    }
    return [];
  };

  const loadWebSettings = () => {
    const saved = localStorage.getItem(STORAGE_KEY_SETTINGS);
    if (saved) {
      try { return JSON.parse(saved); } catch(e) {}
    }
    return {
      daily_goal: 15,
      auto_widget_interval_minutes: 30,
      widget_enabled: true,
      widget_always_on_top: true,
      theme: 'emerald-dark',
      sound_enabled: true,
      streak_count: 1,
      last_study_date: new Date().toISOString().split('T')[0],
      total_reviewed_all_time: 0,
      active_categories: [
        "العقيدة والتوحيد", "فقه العبادات", "الحديث ومصطلحه",
        "علوم القرآن والتفسير", "السيرة النبوية والآداب",
        "أصول الفقه", "اللغة العربية والنحو"
      ]
    };
  };

  const webFallbackInvoke = async (cmd, args) => {
    let cards = await loadWebCards();
    let settings = loadWebSettings();

    switch (cmd) {
      case 'get_cards':
        return cards;

      case 'get_due_cards':
        const now = new Date();
        return cards.filter(c => {
          if (c.state === 'new') return true;
          return new Date(c.due_date) <= now;
        });

      case 'get_random_card': {
        let pool = [...cards];
        if (args.category && args.category !== 'all' && args.category !== 'الكل') {
          pool = pool.filter(c => c.category === args.category);
        }
        if (args.only_due) {
          const nowTime = new Date();
          pool = pool.filter(c => c.state === 'new' || new Date(c.due_date) <= nowTime);
        }
        if (pool.length === 0) return null;
        return pool[Math.floor(Math.random() * pool.length)];
      }

      case 'review_card': {
        const idx = cards.findIndex(c => c.id === args.card_id);
        if (idx === -1) throw new Error('Card not found');
        const card = cards[idx];
        const rating = args.rating;
        const nowIso = new Date().toISOString();
        const nowDate = new Date();

        card.total_reviews = (card.total_reviews || 0) + 1;
        card.last_reviewed = nowIso;

        if (rating === 1) { // Again
          card.lapses = (card.lapses || 0) + 1;
          card.repetitions = 0;
          card.interval = 1;
          card.ease_factor = Math.max(1.3, (card.ease_factor || 2.5) - 0.2);
          card.state = 'learning';
          const due = new Date(nowDate.getTime() + 86400000);
          card.due_date = due.toISOString();
        } else if (rating === 2) { // Hard
          card.ease_factor = Math.max(1.3, (card.ease_factor || 2.5) - 0.15);
          card.interval = Math.max(1, Math.round((card.interval || 1) * 1.2));
          card.repetitions = (card.repetitions || 0) + 1;
          card.state = card.interval >= 21 ? 'mastered' : 'review';
          const due = new Date(nowDate.getTime() + card.interval * 86400000);
          card.due_date = due.toISOString();
        } else if (rating === 3) { // Good
          const rep = card.repetitions || 0;
          card.interval = rep === 0 ? 1 : rep === 1 ? 3 : Math.max(card.interval + 1, Math.round(card.interval * (card.ease_factor || 2.5)));
          card.repetitions = rep + 1;
          card.state = card.interval >= 21 ? 'mastered' : 'review';
          const due = new Date(nowDate.getTime() + card.interval * 86400000);
          card.due_date = due.toISOString();
        } else if (rating === 4) { // Easy
          const rep = card.repetitions || 0;
          card.ease_factor = Math.min(3.5, (card.ease_factor || 2.5) + 0.15);
          card.interval = rep === 0 ? 3 : rep === 1 ? 6 : Math.max(card.interval + 2, Math.round(card.interval * card.ease_factor * 1.3));
          card.repetitions = rep + 1;
          card.state = card.interval >= 21 ? 'mastered' : 'review';
          const due = new Date(nowDate.getTime() + card.interval * 86400000);
          card.due_date = due.toISOString();
        }

        cards[idx] = card;
        localStorage.setItem(STORAGE_KEY_CARDS, JSON.stringify(cards));

        // update settings stats
        settings.total_reviewed_all_time = (settings.total_reviewed_all_time || 0) + 1;
        const todayStr = new Date().toISOString().split('T')[0];
        if (settings.last_study_date !== todayStr) {
          settings.streak_count = (settings.streak_count || 0) + 1;
          settings.last_study_date = todayStr;
        }
        localStorage.setItem(STORAGE_KEY_SETTINGS, JSON.stringify(settings));

        // track today reviews
        let reviews = JSON.parse(localStorage.getItem(STORAGE_KEY_REVIEWS) || '[]');
        reviews.push({ timestamp: nowIso, card_id: card.id, rating });
        localStorage.setItem(STORAGE_KEY_REVIEWS, JSON.stringify(reviews));

        return card;
      }

      case 'check_quiz_answer': {
        const idx = cards.findIndex(c => c.id === args.card_id);
        if (idx === -1) throw new Error('Card not found');
        const card = cards[idx];
        const is_correct = card.correct_index === args.selected_index;
        const rating = is_correct ? 3 : 1;
        const updated = await webFallbackInvoke('review_card', { card_id: args.card_id, rating });
        return {
          is_correct,
          correct_index: card.correct_index,
          explanation: card.explanation,
          answer: card.answer,
          updated_card: updated
        };
      }

      case 'get_stats': {
        const nowDate = new Date();
        const todayStr = nowDate.toISOString().split('T')[0];
        let reviews = JSON.parse(localStorage.getItem(STORAGE_KEY_REVIEWS) || '[]');
        const todayCount = reviews.filter(r => r.timestamp && r.timestamp.startsWith(todayStr)).length;

        let newCards = 0, learningCards = 0, reviewDue = 0, masteredCards = 0;
        const catMap = {};

        cards.forEach(c => {
          catMap[c.category] = (catMap[c.category] || 0) + 1;
          if (c.state === 'new') newCards++;
          else if (c.state === 'learning') learningCards++;
          else if (c.state === 'mastered') masteredCards++;

          if (c.state === 'new' || new Date(c.due_date) <= nowDate) {
            reviewDue++;
          }
        });

        return {
          total_cards: cards.len || cards.length,
          new_cards: newCards,
          learning_cards: learningCards,
          review_due: reviewDue,
          mastered_cards: masteredCards,
          reviewed_today: todayCount,
          daily_goal: settings.daily_goal || 15,
          streak_count: settings.streak_count || 1,
          categories_counts: catMap
        };
      }

      case 'get_settings':
        return settings;

      case 'save_settings':
        localStorage.setItem(STORAGE_KEY_SETTINGS, JSON.stringify(args.settings));
        return true;

      case 'add_card': {
        const newCard = {
          ...args.card,
          id: args.card.id || 'card-' + Date.now(),
          repetitions: 0,
          interval: 0,
          ease_factor: 2.5,
          due_date: new Date().toISOString(),
          state: 'new',
          total_reviews: 0,
          lapses: 0
        };
        cards.push(newCard);
        localStorage.setItem(STORAGE_KEY_CARDS, JSON.stringify(cards));
        return newCard;
      }

      case 'update_card': {
        const idx = cards.findIndex(c => c.id === args.card.id);
        if (idx !== -1) {
          cards[idx] = args.card;
          localStorage.setItem(STORAGE_KEY_CARDS, JSON.stringify(cards));
          return true;
        }
        throw new Error('Card not found');
      }

      case 'delete_card': {
        cards = cards.filter(c => c.id !== args.card_id);
        localStorage.setItem(STORAGE_KEY_CARDS, JSON.stringify(cards));
        return true;
      }

      case 'export_data':
        return JSON.stringify(cards, null, 2);

      case 'import_data': {
        const imported = JSON.parse(args.json_data);
        localStorage.setItem(STORAGE_KEY_CARDS, JSON.stringify(imported));
        return imported.length;
      }

      case 'get_decks': {
        const deckMap = {};
        const nowTime = new Date();
        cards.forEach(c => {
          const dName = c.deck_name || c.category || 'الرزمة الافتراضية';
          if (!deckMap[dName]) {
            deckMap[dName] = { id: 'deck-' + dName, name: dName, description: `رزمة ${dName}`, card_count: 0, due_count: 0 };
          }
          deckMap[dName].card_count++;
          if (c.state === 'new' || new Date(c.due_date) <= nowTime) {
            deckMap[dName].due_count++;
          }
        });
        return Object.values(deckMap);
      }

      case 'get_cards_by_deck': {
        const target = args.deck_name;
        if (!target || target === 'all' || target === 'الكل') return cards;
        return cards.filter(c => (c.deck_name && (c.deck_name === target || c.deck_name.startsWith(target + '::'))) || c.category === target);
      }

      case 'import_anki_package_base64': {
        // Fallback stub for web simulation: if JSON string passed or mock
        return {
          deck_name: args.file_name.replace('.apkg', ''),
          cards_imported: 0,
          notes_imported: 0,
          media_imported: 0,
          decks_found: [args.file_name.replace('.apkg', '')]
        };
      }

      case 'render_anki_template': {
        return window.AnkiTemplateEngine 
          ? window.AnkiTemplateEngine.render(args.template, args.fields, args.cloze_ord, args.is_answer, args.front_side)
          : args.template;
      }

      case 'show_widget':
        window.open('widget.html', '_blank', 'width=440,height=520');
        return true;

      case 'hide_widget':
      case 'close_app':
        return true;

      default:
        console.warn(`Unimplemented command: ${cmd}`);
        return null;
    }
  };

  return {
    isTauri,
    getCards: () => invoke('get_cards'),
    getDueCards: () => invoke('get_due_cards'),
    getRandomCard: (category = null, only_due = false) => invoke('get_random_card', { category, only_due }),
    reviewCard: (card_id, rating) => invoke('review_card', { card_id, rating }),
    checkQuizAnswer: (card_id, selected_index) => invoke('check_quiz_answer', { card_id, selected_index }),
    getStats: () => invoke('get_stats'),
    getSettings: () => invoke('get_settings'),
    saveSettings: (settings) => invoke('save_settings', { settings }),
    addCard: (card) => invoke('add_card', { card }),
    updateCard: (card) => invoke('update_card', { card }),
    deleteCard: (card_id) => invoke('delete_card', { card_id }),
    exportData: () => invoke('export_data'),
    importData: (json_data) => invoke('import_data', { json_data }),
    getDecks: () => invoke('get_decks'),
    getCardsByDeck: (deck_name) => invoke('get_cards_by_deck', { deck_name }),
    importAnkiPackage: (file_path) => invoke('import_anki_package', { file_path }),
    importAnkiPackageBase64: (file_name, base64_data) => invoke('import_anki_package_base64', { file_name, base64_data }),
    renderAnkiTemplate: (template, fields, cloze_ord, is_answer, front_side) => invoke('render_anki_template', { template, fields, cloze_ord, is_answer, front_side }),
    showWidget: () => invoke('show_widget'),
    hideWidget: () => invoke('hide_widget'),
    showMainWindow: () => invoke('show_main_window'),
    closeApp: () => invoke('close_app')
  };
})();

window.ZadBridge = Bridge;
