/**
 * Zad Al-Ilm - Study Session Controller (Anki-like Spaced Repetition)
 */

const StudySession = (() => {
  let cardsQueue = [];
  let currentCardIndex = 0;
  let isAnswerRevealed = false;
  let activeCategory = 'all';

  const init = async (category = 'all') => {
    activeCategory = category;
    currentCardIndex = 0;
    isAnswerRevealed = false;

    const allCards = await ZadBridge.getCards();
    const now = new Date();

    // Filter by deck or category if selected
    let pool = allCards;
    if (category && category !== 'all' && category !== 'الكل') {
      pool = pool.filter(c => 
        c.category === category || 
        c.deck_name === category || 
        (c.deck_name && c.deck_name.startsWith(category + '::'))
      );
    }

    // Prioritize due cards first, then new cards
    const dueCards = pool.filter(c => c.state === 'new' || new Date(c.due_date) <= now);
    cardsQueue = dueCards.length > 0 ? dueCards : pool;

    // Shuffle slightly for varied study
    cardsQueue.sort(() => Math.random() - 0.5);

    renderCard();
    setupKeybindings();
  };

  let lastRenderedFront = '';

  const renderCard = () => {
    const container = document.getElementById('study-card-content');
    const emptyState = document.getElementById('study-empty-state');
    const ratingBar = document.getElementById('study-rating-bar');
    const revealBtnBox = document.getElementById('study-reveal-box');

    if (!cardsQueue || cardsQueue.length === 0 || currentCardIndex >= cardsQueue.length) {
      if (container) container.style.display = 'none';
      if (ratingBar) ratingBar.classList.remove('active');
      if (revealBtnBox) revealBtnBox.style.display = 'none';
      if (emptyState) emptyState.style.display = 'block';
      updateProgress();
      return;
    }

    if (emptyState) emptyState.style.display = 'none';
    if (container) container.style.display = 'flex';

    isAnswerRevealed = false;
    const card = cardsQueue[currentCardIndex];

    // Meta badges
    document.getElementById('study-card-category').textContent = card.deck_name || card.category;
    document.getElementById('study-card-topic').textContent = card.topic || card.template_name || 'مسألة شرعية';
    document.getElementById('study-card-difficulty').textContent = card.note_type || card.difficulty || 'مبتدئ';

    // Check if Anki Template or standard card
    const qEl = document.getElementById('study-question-text');
    const aEl = document.getElementById('study-answer-text');

    if (card.qfmt && card.fields && window.AnkiTemplateEngine) {
      // Anki Template Question
      lastRenderedFront = AnkiTemplateEngine.render(card.qfmt, card.fields, card.cloze_ord, false, null);
      qEl.innerHTML = lastRenderedFront;

      // Anki Template Answer
      const renderedAnswer = AnkiTemplateEngine.render(card.afmt, card.fields, card.cloze_ord, true, lastRenderedFront);
      aEl.innerHTML = renderedAnswer;

      // Apply dynamic CSS
      AnkiTemplateEngine.applyCardCss(card.css);
    } else {
      lastRenderedFront = card.question;
      qEl.textContent = card.question;
      aEl.textContent = card.answer || 'لا توجد إجابة مسجلة';
      if (window.AnkiTemplateEngine) AnkiTemplateEngine.applyCardCss('');
    }

    // Answer & Explanation
    const answerBox = document.getElementById('study-answer-box');
    answerBox.classList.remove('revealed');
    
    const explanationBox = document.getElementById('study-explanation-box');
    if (card.explanation && !card.qfmt) {
      explanationBox.style.display = 'block';
      document.getElementById('study-explanation-text').textContent = card.explanation;
    } else {
      explanationBox.style.display = 'none';
    }

    // Controls
    if (revealBtnBox) revealBtnBox.style.display = 'flex';
    if (ratingBar) ratingBar.classList.remove('active');

    // Update interval estimates on rating buttons
    updateRatingEstimates(card);
    updateProgress();
  };

  const updateRatingEstimates = (card) => {
    const rep = card.repetitions || 0;
    const ease = card.ease_factor || 2.5;
    const interval = card.interval || 0;

    // Again
    document.getElementById('est-again').textContent = '1 يوم';
    // Hard
    const hardDays = Math.max(1, Math.round((interval || 1) * 1.2));
    document.getElementById('est-hard').textContent = `${hardDays} يوم`;
    // Good
    const goodDays = rep === 0 ? 1 : rep === 1 ? 3 : Math.round(interval * ease);
    document.getElementById('est-good').textContent = `${goodDays} يوم`;
    // Easy
    const easyDays = rep === 0 ? 3 : rep === 1 ? 6 : Math.round(interval * ease * 1.3);
    document.getElementById('est-easy').textContent = `${easyDays} يوم`;
  };

  const updateProgress = () => {
    const progressEl = document.getElementById('study-progress-text');
    if (progressEl) {
      progressEl.textContent = `بطاقة ${Math.min(currentCardIndex + 1, cardsQueue.length)} من ${cardsQueue.length}`;
    }
  };

  const revealAnswer = () => {
    if (isAnswerRevealed) return;
    isAnswerRevealed = true;

    const answerBox = document.getElementById('study-answer-box');
    const revealBtnBox = document.getElementById('study-reveal-box');
    const ratingBar = document.getElementById('study-rating-bar');

    if (answerBox) answerBox.classList.add('revealed');
    if (revealBtnBox) revealBtnBox.style.display = 'none';
    if (ratingBar) ratingBar.classList.add('active');
  };

  const submitRating = async (rating) => {
    if (!cardsQueue || currentCardIndex >= cardsQueue.length) return;
    const card = cardsQueue[currentCardIndex];

    try {
      await ZadBridge.reviewCard(card.id, rating);
      if (window.App) window.App.refreshTopBar();
    } catch (err) {
      console.error('Error submitting review:', err);
    }

    currentCardIndex++;
    renderCard();
  };

  const setupKeybindings = () => {
    document.removeEventListener('keydown', handleKeyDown);
    document.addEventListener('keydown', handleKeyDown);
  };

  const handleKeyDown = (e) => {
    // Only handle if study view is active
    const studySection = document.getElementById('view-study');
    if (!studySection || !studySection.classList.contains('active')) return;

    if (e.code === 'Space') {
      e.preventDefault();
      if (!isAnswerRevealed) {
        revealAnswer();
      }
    } else if (isAnswerRevealed) {
      if (e.key === '1') submitRating(1);
      else if (e.key === '2') submitRating(2);
      else if (e.key === '3') submitRating(3);
      else if (e.key === '4') submitRating(4);
    }
  };

  return {
    init,
    revealAnswer,
    submitRating
  };
})();

window.StudySession = StudySession;
