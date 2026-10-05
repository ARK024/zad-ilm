/**
 * Zad Al-Ilm - Interactive Quiz Controller (Instant correction & proofs)
 */

const QuizSession = (() => {
  let quizCards = [];
  let currentIndex = 0;
  let score = 0;
  let totalAnswered = 0;
  let isAnswered = false;

  const init = async (category = 'all') => {
    currentIndex = 0;
    score = 0;
    totalAnswered = 0;
    isAnswered = false;

    const allCards = await ZadBridge.getCards();
    // Filter quiz type questions with options
    let pool = allCards.filter(c => c.type === 'quiz' && c.options && c.options.length > 0);

    if (category && category !== 'all' && category !== 'الكل') {
      pool = pool.filter(c => c.category === category);
    }

    // Shuffle
    quizCards = pool.sort(() => Math.random() - 0.5);

    updateScoreDisplay();
    renderQuestion();
    setupKeybindings();
  };

  const renderQuestion = () => {
    isAnswered = false;
    const qBox = document.getElementById('quiz-question-box');
    const emptyState = document.getElementById('quiz-empty-state');
    const proofBox = document.getElementById('quiz-proof-box');
    const nextBar = document.getElementById('quiz-next-bar');

    if (proofBox) proofBox.classList.remove('active');
    if (nextBar) nextBar.classList.remove('active');

    if (!quizCards || quizCards.length === 0 || currentIndex >= quizCards.length) {
      if (qBox) qBox.style.display = 'none';
      if (emptyState) emptyState.style.display = 'block';
      return;
    }

    if (emptyState) emptyState.style.display = 'none';
    if (qBox) qBox.style.display = 'block';

    const card = quizCards[currentIndex];

    // Meta
    document.getElementById('quiz-card-category').textContent = card.category;
    document.getElementById('quiz-card-topic').textContent = card.topic || 'اختبار فهم';
    document.getElementById('quiz-question-text').textContent = card.question;

    // Render Options
    const optionsContainer = document.getElementById('quiz-options-list');
    optionsContainer.innerHTML = '';

    const letters = ['أ', 'ب', 'ج', 'د', 'هـ'];
    card.options.forEach((optText, idx) => {
      const btn = document.createElement('button');
      btn.className = 'quiz-opt-btn';
      btn.innerHTML = `
        <span class="quiz-opt-idx">${letters[idx] || (idx + 1)}</span>
        <span class="quiz-opt-text">${escapeHtml(optText)}</span>
      `;
      btn.onclick = () => selectOption(idx);
      optionsContainer.appendChild(btn);
    });

    // Update progress
    document.getElementById('quiz-progress-text').textContent = `سؤال ${currentIndex + 1} من ${quizCards.length}`;
  };

  const selectOption = async (selectedIndex) => {
    if (isAnswered) return;
    isAnswered = true;

    const card = quizCards[currentIndex];
    const optionBtns = document.querySelectorAll('.quiz-opt-btn');
    optionBtns.forEach(b => b.disabled = true);

    try {
      const result = await ZadBridge.checkQuizAnswer(card.id, selectedIndex);
      totalAnswered++;

      if (result.is_correct) {
        score++;
        optionBtns[selectedIndex].classList.add('correct');
      } else {
        optionBtns[selectedIndex].classList.add('wrong');
        if (result.correct_index >= 0 && result.correct_index < optionBtns.length) {
          optionBtns[result.correct_index].classList.add('correct');
        }
      }

      // Show proof & scholarly explanation
      const proofBox = document.getElementById('quiz-proof-box');
      const proofText = document.getElementById('quiz-proof-text');
      if (proofBox && proofText) {
        proofText.textContent = result.explanation || result.answer || 'تمت الإجابة بنجاح.';
        proofBox.classList.add('active');
      }

      // Show next button
      const nextBar = document.getElementById('quiz-next-bar');
      if (nextBar) nextBar.classList.add('active');

      updateScoreDisplay();
      if (window.App) window.App.refreshTopBar();

    } catch (err) {
      console.error('Quiz answer error:', err);
    }
  };

  const nextQuestion = () => {
    currentIndex++;
    renderQuestion();
  };

  const updateScoreDisplay = () => {
    const scoreEl = document.getElementById('quiz-score-val');
    const accuracyEl = document.getElementById('quiz-accuracy-val');
    if (scoreEl) scoreEl.textContent = `${score} / ${totalAnswered}`;
    if (accuracyEl) {
      const acc = totalAnswered > 0 ? Math.round((score / totalAnswered) * 100) : 100;
      accuracyEl.textContent = `${acc}%`;
    }
  };

  const setupKeybindings = () => {
    document.removeEventListener('keydown', handleKeyDown);
    document.addEventListener('keydown', handleKeyDown);
  };

  const handleKeyDown = (e) => {
    const quizSection = document.getElementById('view-quiz');
    if (!quizSection || !quizSection.classList.contains('active')) return;

    if (!isAnswered) {
      if (e.key === '1') selectOption(0);
      else if (e.key === '2') selectOption(1);
      else if (e.key === '3') selectOption(2);
      else if (e.key === '4') selectOption(3);
    } else {
      if (e.code === 'Space' || e.key === 'Enter') {
        e.preventDefault();
        nextQuestion();
      }
    }
  };

  const escapeHtml = (text) => {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  };

  return {
    init,
    nextQuestion,
    selectOption
  };
})();

window.QuizSession = QuizSession;
