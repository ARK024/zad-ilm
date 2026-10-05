/**
 * Zad Al-Ilm - Floating Desktop Widget Controller
 */

const DesktopWidget = (() => {
  let currentCard = null;
  let isAnswerRevealed = false;
  let isQuizAnswered = false;

  const init = async () => {
    setupButtons();
    await loadNextCard();
    await updateDueCount();
  };

  const updateDueCount = async () => {
    try {
      const stats = await ZadBridge.getStats();
      const dueEl = document.getElementById('w-due-count');
      if (dueEl) dueEl.textContent = stats.review_due || 0;
    } catch(e) {}
  };

  const loadNextCard = async () => {
    isAnswerRevealed = false;
    isQuizAnswered = false;

    // Reset UI
    const answerBox = document.getElementById('w-answer-box');
    const revealBtn = document.getElementById('w-reveal-btn');
    const ratingGrid = document.getElementById('w-rating-grid');
    const optionsList = document.getElementById('w-options-list');

    if (answerBox) answerBox.classList.remove('active');
    if (revealBtn) revealBtn.style.display = 'block';
    if (ratingGrid) ratingGrid.classList.remove('active');
    if (optionsList) optionsList.innerHTML = '';

    // Fetch random card (prefer due)
    currentCard = await ZadBridge.getRandomCard(null, true);
    if (!currentCard) {
      currentCard = await ZadBridge.getRandomCard(null, false);
    }

    if (!currentCard) {
      document.getElementById('w-question-text').textContent = 'لا توجد مسائل حالياً، أحسنت!';
      if (revealBtn) revealBtn.style.display = 'none';
      return;
    }

    // Set meta & question
    document.getElementById('w-category-badge').textContent = currentCard.deck_name || currentCard.category;

    const qEl = document.getElementById('w-question-text');
    const aEl = document.getElementById('w-answer-text');
    const expEl = document.getElementById('w-explanation-text');

    if (currentCard.qfmt && currentCard.fields && window.AnkiTemplateEngine) {
      const renderedQ = AnkiTemplateEngine.render(currentCard.qfmt, currentCard.fields, currentCard.cloze_ord, false, null);
      qEl.innerHTML = renderedQ;
      const renderedA = AnkiTemplateEngine.render(currentCard.afmt, currentCard.fields, currentCard.cloze_ord, true, renderedQ);
      aEl.innerHTML = renderedA;
      expEl.textContent = '';
    } else {
      qEl.textContent = currentCard.question;
      aEl.textContent = currentCard.answer || '';
      expEl.textContent = currentCard.explanation || '';
    }

    // If quiz with options
    if (currentCard.type === 'quiz' && currentCard.options && currentCard.options.length > 0) {
      if (revealBtn) revealBtn.style.display = 'none';
      renderQuizOptions(currentCard.options);
    } else {
      if (revealBtn) revealBtn.style.display = 'block';
    }

    updateDueCount();
  };

  const renderQuizOptions = (options) => {
    const list = document.getElementById('w-options-list');
    list.innerHTML = '';
    const letters = ['أ', 'ب', 'ج', 'د'];

    options.forEach((optText, idx) => {
      const btn = document.createElement('button');
      btn.className = 'w-opt-btn';
      btn.textContent = `${letters[idx] || (idx + 1)}. ${optText}`;
      btn.onclick = () => selectQuizOption(idx);
      list.appendChild(btn);
    });
  };

  const selectQuizOption = async (selectedIndex) => {
    if (isQuizAnswered || !currentCard) return;
    isQuizAnswered = true;

    const btns = document.querySelectorAll('.w-opt-btn');
    btns.forEach(b => b.disabled = true);

    try {
      const res = await ZadBridge.checkQuizAnswer(currentCard.id, selectedIndex);
      if (res.is_correct) {
        btns[selectedIndex].classList.add('correct');
      } else {
        btns[selectedIndex].classList.add('wrong');
        if (res.correct_index >= 0 && res.correct_index < btns.length) {
          btns[res.correct_index].classList.add('correct');
        }
      }

      // Show proof / explanation
      const answerBox = document.getElementById('w-answer-box');
      if (answerBox) answerBox.classList.add('active');

      // Next button
      const revealBtn = document.getElementById('w-reveal-btn');
      if (revealBtn) {
        revealBtn.textContent = 'المسألة التالية ⬅';
        revealBtn.style.display = 'block';
        revealBtn.onclick = () => {
          revealBtn.textContent = 'كشف الإجابة الشرعية';
          revealBtn.onclick = revealAnswer;
          loadNextCard();
        };
      }
    } catch (e) {
      console.error(e);
    }
  };

  const revealAnswer = () => {
    if (isAnswerRevealed) return;
    isAnswerRevealed = true;

    const answerBox = document.getElementById('w-answer-box');
    const revealBtn = document.getElementById('w-reveal-btn');
    const ratingGrid = document.getElementById('w-rating-grid');

    if (answerBox) answerBox.classList.add('active');
    if (revealBtn) revealBtn.style.display = 'none';
    if (ratingGrid) ratingGrid.classList.add('active');
  };

  const rateCard = async (rating) => {
    if (!currentCard) return;
    try {
      await ZadBridge.reviewCard(currentCard.id, rating);
    } catch(e) {
      console.error(e);
    }
    loadNextCard();
  };

  const setupButtons = () => {
    const revealBtn = document.getElementById('w-reveal-btn');
    if (revealBtn) revealBtn.onclick = revealAnswer;

    document.getElementById('w-btn-again')?.addEventListener('click', () => rateCard(1));
    document.getElementById('w-btn-hard')?.addEventListener('click', () => rateCard(2));
    document.getElementById('w-btn-good')?.addEventListener('click', () => rateCard(3));
    document.getElementById('w-btn-easy')?.addEventListener('click', () => rateCard(4));

    document.getElementById('w-btn-close')?.addEventListener('click', () => {
      ZadBridge.hideWidget();
    });

    document.getElementById('w-btn-expand')?.addEventListener('click', () => {
      ZadBridge.showMainWindow();
      ZadBridge.hideWidget();
    });

    document.getElementById('w-btn-next')?.addEventListener('click', () => {
      loadNextCard();
    });
  };

  return {
    init,
    loadNextCard,
    revealAnswer,
    rateCard
  };
})();

document.addEventListener('DOMContentLoaded', () => {
  DesktopWidget.init();
});
