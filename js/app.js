// app.js
// Uygulamanin ana orkestratoru: ekran yonlendirme, veri yukleme, mod
// baslatma, sonuc/istatistik/kelime/ayarlar ekranlarinin baglanmasi.
import {
  getState, subscribe, getDueQuestionIds, getWrongQuestionIds,
  exportStateAsJSON, importStateFromJSON, resetAllProgress,
  recordWordAnswer, getDueWords, isWordSaved,
} from "./storage.js";
import { Quiz, renderQuestionInto, markOptionResult, formatExplanation, formatTime } from "./quiz.js";
import { initDictionarySheet, wrapWords, getVocabFrequency, getDictionaryEntry } from "./dictionary.js";
import * as stats from "./stats.js";

const TYPE_LABELS = stats.typeLabel;
const ALL_TYPES = [
  "vocabulary", "cloze", "sentence_completion", "translation_en_tr",
  "translation_tr_en", "reading", "dialogue", "restatement",
  "paragraph_completion", "irrelevant_sentence",
];

const questionCache = new Map(); // id -> question
const loadedByType = new Set();
const loadedSessions = new Set();
let questionIndex = null; // data/questions/index.json
let currentQuiz = null;
let currentQuizMeta = null; // {mode, sourceType, sourceId, questionIds, deferFeedback, timeLimitMs}
let reviewQueue = null; // yanlislari gozden gecirme icin

const INPROGRESS_KEY = "yds-app-inprogress-v1";

// ---------------------------------------------------------------------------
// Veri yukleme
// ---------------------------------------------------------------------------

async function loadIndex() {
  if (questionIndex) return questionIndex;
  const res = await fetch("data/questions/index.json");
  questionIndex = await res.json();
  return questionIndex;
}

async function loadByType(type) {
  if (loadedByType.has(type)) return;
  const res = await fetch(`data/questions/by-type/${type}.json`);
  if (!res.ok) return;
  const list = await res.json();
  list.forEach((q) => questionCache.set(q.id, q));
  loadedByType.add(type);
}

async function loadSession(sessionId) {
  if (loadedSessions.has(sessionId)) return;
  const res = await fetch(`data/questions/${sessionId}.json`);
  if (!res.ok) return;
  const list = await res.json();
  list.forEach((q) => questionCache.set(q.id, q));
  loadedSessions.add(sessionId);
}

function sessionIdFromQuestionId(qid) {
  const m = qid.match(/^(.*)-q\d+$/);
  return m ? m[1] : null;
}

// ---------------------------------------------------------------------------
// Ekran yonlendirme
// ---------------------------------------------------------------------------

const NAV_HIDDEN_SCREENS = new Set(["screen-quiz", "screen-vocab", "screen-type-select", "screen-result"]);

function showScreen(id) {
  document.querySelectorAll(".screen").forEach((el) => el.classList.remove("is-active"));
  document.getElementById(id).classList.add("is-active");
  document.getElementById("bottom-nav").style.display = NAV_HIDDEN_SCREENS.has(id) ? "none" : "flex";
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.nav === id.replace("screen-", ""));
  });
  window.scrollTo(0, 0);
}

// ---------------------------------------------------------------------------
// Ana ekran
// ---------------------------------------------------------------------------

async function refreshHomeScreen() {
  const dueQ = getDueQuestionIds().length;
  const dueW = getDueWords().length;
  document.getElementById("due-count").textContent = String(dueQ + dueW);

  const wrongCount = getWrongQuestionIds().length;
  document.getElementById("wrong-count-label").textContent =
    wrongCount > 0 ? `${wrongCount} soru` : "Henuz yanlis yok";

  document.getElementById("due-count-label").textContent =
    dueQ + dueW > 0 ? `${dueQ + dueW} soru bekliyor` : "Bugun tekrar yok";

  const weak = stats.weakestType();
  document.getElementById("weak-type-label").textContent = weak
    ? `${TYPE_LABELS(weak.type)} (%${Math.round(weak.rate * 100)})`
    : "Henuz yeterli veri yok";

  const inProgress = loadInProgress();
  const banner = document.getElementById("continue-banner");
  if (inProgress) {
    banner.hidden = false;
    document.getElementById("continue-info").textContent =
      `${modeLabel(inProgress.mode)} - soru ${inProgress.index + 1}/${inProgress.questionIds.length}`;
  } else {
    banner.hidden = true;
  }
}

function modeLabel(mode) {
  return {
    mock: "Tam deneme", type: "Tek tip calisma", wrong: "Yanlislarim",
    due: "Bugunun tekrari", weak: "Zayif yonum",
  }[mode] || mode;
}

// ---------------------------------------------------------------------------
// Devam eden test (resume) kalicilastirma
// ---------------------------------------------------------------------------

function saveInProgress() {
  if (!currentQuiz || !currentQuizMeta) return;
  const snapshot = {
    ...currentQuizMeta,
    index: currentQuiz.index,
    answers: currentQuiz.answers,
    remainingMs: currentQuizMeta.timeLimitMs ? currentQuiz.getRemainingMs() : null,
  };
  localStorage.setItem(INPROGRESS_KEY, JSON.stringify(snapshot));
}

function clearInProgress() {
  localStorage.removeItem(INPROGRESS_KEY);
}

function loadInProgress() {
  try {
    const raw = localStorage.getItem(INPROGRESS_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

async function resumeInProgress() {
  const snap = loadInProgress();
  if (!snap) return;
  await ensureQuestionsLoaded(snap.sourceType, snap.sourceId);
  const questions = snap.questionIds.map((id) => questionCache.get(id)).filter(Boolean);
  if (questions.length !== snap.questionIds.length) {
    clearInProgress();
    return;
  }
  beginQuiz(questions, {
    mode: snap.mode, sourceType: snap.sourceType, sourceId: snap.sourceId,
    deferFeedback: snap.deferFeedback, timeLimitMs: snap.remainingMs ?? snap.timeLimitMs,
    resumeIndex: snap.index, resumeAnswers: snap.answers,
  });
}

async function ensureQuestionsLoaded(sourceType, sourceId) {
  if (sourceType === "type") await loadByType(sourceId);
  else if (sourceType === "session") await loadSession(sourceId);
  else if (sourceType === "sessions") {
    for (const sid of sourceId) await loadSession(sid);
  }
}

// ---------------------------------------------------------------------------
// Test baslatma modlari
// ---------------------------------------------------------------------------

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

async function startMock(sessionId) {
  await loadSession(sessionId);
  const questions = getQuestionsForSession(sessionId);
  beginQuiz(questions, {
    mode: "mock", sourceType: "session", sourceId: sessionId,
    deferFeedback: true, timeLimitMs: 180 * 60 * 1000,
  });
}

function getQuestionsForSession(sessionId) {
  const list = [];
  for (const q of questionCache.values()) {
    if (sessionIdFromQuestionId(q.id) === sessionId) list.push(q);
  }
  list.sort((a, b) => a.source.number - b.source.number);
  return list;
}

async function startTypeStudy(type, count = 20) {
  await loadByType(type);
  const all = [...questionCache.values()].filter((q) => q.type === type);
  const questions = shuffle(all).slice(0, count);
  beginQuiz(questions, {
    mode: "type", sourceType: "type", sourceId: type,
    deferFeedback: false, timeLimitMs: null,
  });
}

async function startWeakTypeStudy() {
  const weak = stats.weakestType();
  const type = weak ? weak.type : ALL_TYPES[Math.floor(Math.random() * ALL_TYPES.length)];
  await startTypeStudy(type, 30);
}

async function startWrongReview() {
  const ids = getWrongQuestionIds();
  if (ids.length === 0) {
    alert("Henuz yanlis cevaplanmis soru yok.");
    return;
  }
  const sessions = [...new Set(ids.map(sessionIdFromQuestionId).filter(Boolean))];
  for (const sid of sessions) await loadSession(sid);
  const questions = ids.map((id) => questionCache.get(id)).filter(Boolean);
  beginQuiz(shuffle(questions), {
    mode: "wrong", sourceType: "sessions", sourceId: sessions,
    deferFeedback: false, timeLimitMs: null,
  });
}

async function startDueReview() {
  const ids = getDueQuestionIds();
  if (ids.length === 0) {
    alert("Su an tekrar bekleyen soru yok.");
    return;
  }
  const sessions = [...new Set(ids.map(sessionIdFromQuestionId).filter(Boolean))];
  for (const sid of sessions) await loadSession(sid);
  const questions = ids.map((id) => questionCache.get(id)).filter(Boolean);
  beginQuiz(shuffle(questions), {
    mode: "due", sourceType: "sessions", sourceId: sessions,
    deferFeedback: false, timeLimitMs: null,
  });
}

// ---------------------------------------------------------------------------
// Test ekrani (Quiz motoru baglanmasi)
// ---------------------------------------------------------------------------

const els = {};
function cacheEls() {
  els.passage = document.getElementById("quiz-passage");
  els.stem = document.getElementById("quiz-stem");
  els.options = document.getElementById("quiz-options");
  els.progressBar = document.getElementById("quiz-progress-bar");
  els.counter = document.getElementById("quiz-counter");
  els.timer = document.getElementById("quiz-timer");
  els.explanationCard = document.getElementById("quiz-explanation");
  els.explanationBadge = document.getElementById("explanation-badge");
  els.explanationCorrect = document.getElementById("explanation-correct");
  els.explanationDistractor = document.getElementById("explanation-distractor");
  els.explanationTakeaway = document.getElementById("explanation-takeaway");
  els.nextBtn = document.getElementById("quiz-next");
}

function beginQuiz(questions, meta) {
  if (questions.length === 0) {
    alert("Bu mod icin yeterli soru bulunamadi.");
    return;
  }
  currentQuizMeta = meta;
  currentQuiz = new Quiz({
    questions,
    deferFeedback: meta.deferFeedback,
    timeLimitMs: meta.timeLimitMs,
    onRender: onQuizRender,
    onAnswer: onQuizAnswer,
    onFinish: onQuizFinish,
    onTick: onQuizTick,
  });
  currentQuizMeta.questionIds = questions.map((q) => q.id);

  if (meta.resumeIndex != null) {
    currentQuiz.index = Math.min(meta.resumeIndex, questions.length - 1);
    currentQuiz.answers = meta.resumeAnswers || currentQuiz.answers;
  }

  showScreen("screen-quiz");
  els.timer.hidden = !meta.timeLimitMs;
  currentQuiz.start();
}

function onQuizRender(question, index, total) {
  els.progressBar.style.width = `${(index / total) * 100}%`;
  els.counter.textContent = `${index + 1}/${total}`;
  renderQuestionInto(question, { passageEl: els.passage, stemEl: els.stem, optionsEl: els.options });
  els.explanationCard.hidden = true;
  els.nextBtn.hidden = true;

  const prevAnswer = currentQuiz.answers[index];
  if (prevAnswer) {
    // devam edilen bir testte zaten cevaplanmis soru: sonucu tekrar goster
    applyAnswerVisuals(prevAnswer);
  }
  saveInProgress();
}

function onQuizTick(remainingMs) {
  els.timer.textContent = `Kalan sure: ${formatTime(remainingMs)}`;
  els.timer.classList.toggle("is-low", remainingMs < 5 * 60 * 1000);
}

function onQuizAnswer(result) {
  applyAnswerVisuals(result);
  saveInProgress();
}

function applyAnswerVisuals(result) {
  const q = result.question;
  if (!currentQuizMeta.deferFeedback) {
    markOptionResult(els.options, { selected: result.selected, correctIndex: q.answer });
    const info = formatExplanation(q, result.selected);
    els.explanationBadge.textContent = result.isCorrect ? "Dogru" : "Yanlis";
    els.explanationBadge.style.color = result.isCorrect ? "var(--correct)" : "var(--wrong)";
    els.explanationCorrect.textContent = info.correct;
    els.explanationDistractor.textContent = info.distractorText;
    els.explanationDistractor.hidden = !info.distractorText;
    els.explanationTakeaway.textContent = info.takeaway ? `Kural: ${info.takeaway}` : "";
    els.explanationCard.hidden = false;
  } else {
    // deneme modu: sadece secim isaretlensin, dogru/yanlis gizli kalsin
    els.options.querySelectorAll(".option").forEach((row) => {
      row.classList.toggle("is-selected", Number(row.dataset.index) === result.selected);
      row.querySelector(".option-letter").disabled = true;
    });
  }
  els.nextBtn.hidden = false;
}

function onQuizFinish(summary) {
  clearInProgress();
  renderResultScreen(summary);
  showScreen("screen-result");
  refreshHomeScreen();
}

// ---------------------------------------------------------------------------
// Sonuc ekrani
// ---------------------------------------------------------------------------

function renderResultScreen(summary) {
  const body = document.getElementById("result-body");
  const isFullMock = currentQuizMeta.mode === "mock";
  const score = isFullMock
    ? stats.examScoreFromCorrectCount(summary.correct, summary.total)
    : Math.round((summary.correct / Math.max(1, summary.answered)) * 100);

  const byType = {};
  summary.answers.forEach((a) => {
    if (!a) return;
    const t = a.question.type || "unknown";
    byType[t] = byType[t] || { seen: 0, correct: 0 };
    byType[t].seen += 1;
    if (a.isCorrect) byType[t].correct += 1;
  });

  let html = `<div class="result-score">
      <div class="big">${summary.correct}/${summary.total}</div>
      <div class="label">${isFullMock ? `Tahmini YDS puani: ${score}` : `%${score} dogruluk`}</div>
    </div>
    <div class="result-row"><span>Toplam sure</span><span>${formatTime(summary.totalTimeMs)}</span></div>`;

  Object.entries(byType).forEach(([t, v]) => {
    html += `<div class="result-row"><span>${TYPE_LABELS(t)}</span><span>${v.correct}/${v.seen}</span></div>`;
  });

  body.innerHTML = html;

  if (isFullMock) {
    import("./storage.js").then(({ recordSessionSummary }) => {
      recordSessionSummary({ mode: "mock", correct: summary.correct, total: summary.total, score });
    });
  }
}

function startReviewOfWrong() {
  const wrongAnswers = currentQuiz.answers.filter((a) => a && !a.isCorrect);
  if (wrongAnswers.length === 0) {
    alert("Bu testte yanlisin yok, tebrikler!");
    return;
  }
  reviewQueue = { answers: wrongAnswers, index: 0 };
  showScreen("screen-quiz");
  document.getElementById("quiz-next").textContent = "Sonraki";
  els.timer.hidden = true;
  renderReviewItem();
}

function renderReviewItem() {
  const { answers, index } = reviewQueue;
  const a = answers[index];
  els.progressBar.style.width = `${(index / answers.length) * 100}%`;
  els.counter.textContent = `${index + 1}/${answers.length}`;
  renderQuestionInto(a.question, { passageEl: els.passage, stemEl: els.stem, optionsEl: els.options });
  markOptionResult(els.options, { selected: a.selected, correctIndex: a.question.answer });
  const info = formatExplanation(a.question, a.selected);
  els.explanationBadge.textContent = "Yanlis yaptigin soru";
  els.explanationBadge.style.color = "var(--wrong)";
  els.explanationCorrect.textContent = info.correct;
  els.explanationDistractor.textContent = info.distractorText;
  els.explanationDistractor.hidden = !info.distractorText;
  els.explanationTakeaway.textContent = info.takeaway ? `Kural: ${info.takeaway}` : "";
  els.explanationCard.hidden = false;
  els.nextBtn.hidden = false;
}

function reviewNext() {
  reviewQueue.index += 1;
  if (reviewQueue.index >= reviewQueue.answers.length) {
    reviewQueue = null;
    document.getElementById("quiz-next").textContent = "Sonraki soru";
    showScreen("screen-result");
    return;
  }
  renderReviewItem();
}

// ---------------------------------------------------------------------------
// Tip / deneme secim ekrani
// ---------------------------------------------------------------------------

async function openTypeSelect() {
  await loadIndex();
  const list = document.getElementById("type-list");
  list.innerHTML = "";
  document.querySelector("#screen-type-select h2").textContent = "Soru turu sec";
  ALL_TYPES.forEach((type) => {
    const count = questionIndex.types[type] || 0;
    const item = document.createElement("button");
    item.className = "type-item";
    item.innerHTML = `<span>${TYPE_LABELS(type)}</span><span class="count">${count} soru</span>`;
    item.addEventListener("click", () => startTypeStudy(type));
    list.appendChild(item);
  });
  showScreen("screen-type-select");
}

async function openMockSelect() {
  await loadIndex();
  const list = document.getElementById("type-list");
  list.innerHTML = "";
  document.querySelector("#screen-type-select h2").textContent = "Hangi oturum?";
  questionIndex.sessions.forEach((s) => {
    const item = document.createElement("button");
    item.className = "type-item";
    item.innerHTML = `<span>${s.id}</span><span class="count">${s.count} soru</span>`;
    item.addEventListener("click", () => startMock(s.id));
    list.appendChild(item);
  });
  showScreen("screen-type-select");
}

// ---------------------------------------------------------------------------
// Istatistik ekrani
// ---------------------------------------------------------------------------

async function renderStatsScreen() {
  const body = document.getElementById("stats-body");
  const total = stats.totalAnswered();
  if (total === 0) {
    body.innerHTML = '<p class="empty-state">Henuz hic soru cozulmedi. Bir mod secip calismaya basla.</p>';
    return;
  }

  const uniqueTypes = new Set(getState().answerLog.map((e) => e.type).filter(Boolean));
  for (const t of uniqueTypes) await loadByType(t);

  const estScore = stats.estimatedCurrentScore();
  const byType = stats.accuracyByType();
  const timeByType = stats.avgTimeByType();
  const timeline = stats.accuracyOverTime(20);
  const takeaways = stats.topMissedTakeaways(questionCache, 8);

  let html = `<div class="score-hero">
      <div class="big">${estScore != null ? Math.round(estScore) : "-"}</div>
      <div class="label">Su an sinava girsen tahmini puan (son 200 soruya gore)</div>
    </div>`;

  html += '<div class="stats-section"><h3>Tipe gore dogruluk (zayiftan guclu)</h3>';
  byType.forEach((t) => {
    html += barRow(TYPE_LABELS(t.type), t.rate, `%${Math.round(t.rate * 100)}`);
  });
  html += "</div>";

  html += '<div class="stats-section"><h3>Soru basina ortalama sure</h3>';
  const maxTime = Math.max(...timeByType.map((t) => t.avgMs), 1);
  timeByType.forEach((t) => {
    html += barRow(TYPE_LABELS(t.type), t.avgMs / maxTime, formatTime(t.avgMs));
  });
  html += "</div>";

  if (timeline.length > 1) {
    html += '<div class="stats-section"><h3>Zaman icinde dogruluk (her cubuk ~20 soru)</h3><div class="timeline-bars">';
    timeline.forEach((b) => {
      html += `<div class="timeline-bar" style="height:${Math.max(4, b.rate * 80)}px" title="%${Math.round(b.rate * 100)}"></div>`;
    });
    html += "</div></div>";
  }

  html += '<div class="stats-section"><h3>En cok yanlis yapilan kurallar</h3>';
  if (takeaways.length === 0) {
    html += '<p class="empty-state">Henuz yeterli aciklamali yanlis yok.</p>';
  } else {
    takeaways.forEach((t) => {
      html += `<div class="takeaway-item"><span class="count">${t.count}x</span>${t.takeaway}</div>`;
    });
  }
  html += "</div>";

  body.innerHTML = html;
}

function barRow(label, rate01, valueText) {
  const pct = Math.max(0, Math.min(1, rate01)) * 100;
  return `<div class="stat-bar-row">
      <span class="stat-label">${label}</span>
      <span class="stat-bar-track"><span class="stat-bar-fill" style="width:${pct}%"></span></span>
      <span class="stat-bar-value">${valueText}</span>
    </div>`;
}

// ---------------------------------------------------------------------------
// Kelime modu
// ---------------------------------------------------------------------------

let vocabQueue = [];
let vocabPos = 0;

async function openVocabMode() {
  const freq = await getVocabFrequency();
  const dueWords = new Set(getDueWords());
  const priorityWords = freq.filter((e) => dueWords.has(e.word));
  const restWords = freq.filter((e) => !dueWords.has(e.word));
  vocabQueue = [...priorityWords, ...restWords].slice(0, 200);
  vocabPos = 0;
  showScreen("screen-vocab");
  renderVocabCard();
}

async function renderVocabCard() {
  if (vocabPos >= vocabQueue.length) {
    showScreen("screen-home");
    refreshHomeScreen();
    return;
  }
  const entry = vocabQueue[vocabPos];
  document.getElementById("vocab-progress").textContent = `${vocabPos + 1}/${vocabQueue.length}`;
  document.getElementById("vocab-word").textContent = entry.word;
  document.getElementById("vocab-exam-count").textContent = `${entry.examCount} sinavda cikti (${entry.count} kez)`;
  document.getElementById("vocab-reveal").hidden = true;
  document.getElementById("vocab-show-btn").hidden = false;
  document.getElementById("vocab-answer-buttons").hidden = true;

  const dictEntry = await getDictionaryEntry(entry.word);
  document.getElementById("vocab-translation").textContent = dictEntry?.translation || "Sozluk kaydi yok";
  document.getElementById("vocab-pos").textContent = dictEntry?.partOfSpeech || "";
  document.getElementById("vocab-example").textContent = dictEntry?.example || "";

  const linksEl = document.getElementById("vocab-links");
  linksEl.innerHTML = "";
  entry.questionIds.slice(0, 5).forEach((qid) => {
    const btn = document.createElement("button");
    btn.className = "word-sheet-link";
    btn.textContent = qid;
    btn.addEventListener("click", () => navigateToQuestion(qid));
    linksEl.appendChild(btn);
  });
}

function wireVocabScreen() {
  document.getElementById("vocab-show-btn").addEventListener("click", () => {
    document.getElementById("vocab-reveal").hidden = false;
    document.getElementById("vocab-show-btn").hidden = true;
    document.getElementById("vocab-answer-buttons").hidden = false;
  });
  document.getElementById("vocab-know").addEventListener("click", () => {
    recordWordAnswer(vocabQueue[vocabPos].word, true);
    vocabPos += 1;
    renderVocabCard();
  });
  document.getElementById("vocab-dont-know").addEventListener("click", () => {
    recordWordAnswer(vocabQueue[vocabPos].word, false);
    vocabPos += 1;
    renderVocabCard();
  });
}

async function navigateToQuestion(qid) {
  const sessionId = sessionIdFromQuestionId(qid);
  if (sessionId) await loadSession(sessionId);
  const q = questionCache.get(qid);
  if (!q) return;
  beginQuiz([q], { mode: "lookup", sourceType: "session", sourceId: sessionId, deferFeedback: false, timeLimitMs: null });
}

// ---------------------------------------------------------------------------
// Ayarlar
// ---------------------------------------------------------------------------

function wireSettingsScreen() {
  document.getElementById("export-btn").addEventListener("click", () => {
    const blob = new Blob([exportStateAsJSON()], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `yds-ilerleme-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("import-input").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const text = await file.text();
    try {
      importStateFromJSON(text);
      alert("Ilerleme ice aktarildi.");
      refreshHomeScreen();
    } catch (err) {
      alert("Dosya okunamadi: " + err.message);
    }
  });

  document.getElementById("reset-btn").addEventListener("click", () => {
    if (confirm("Tum ilerleme silinecek. Emin misin?")) {
      resetAllProgress();
      clearInProgress();
      refreshHomeScreen();
    }
  });
}

// ---------------------------------------------------------------------------
// Genel baglantilar
// ---------------------------------------------------------------------------

function wireNav() {
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = `screen-${btn.dataset.nav}`;
      showScreen(target);
      if (target === "screen-stats") renderStatsScreen();
      if (target === "screen-home") refreshHomeScreen();
    });
  });

  document.querySelectorAll("[data-back]").forEach((btn) => {
    btn.addEventListener("click", () => {
      showScreen("screen-home");
      refreshHomeScreen();
    });
  });

  document.querySelectorAll(".mode-card").forEach((card) => {
    card.addEventListener("click", () => {
      const mode = card.dataset.mode;
      if (mode === "mock") openMockSelect();
      else if (mode === "type") openTypeSelect();
      else if (mode === "wrong") startWrongReview();
      else if (mode === "due") startDueReview();
      else if (mode === "weak") startWeakTypeStudy();
      else if (mode === "vocab") openVocabMode();
    });
  });

  document.getElementById("continue-btn").addEventListener("click", resumeInProgress);

  document.getElementById("quiz-exit").addEventListener("click", () => {
    showScreen("screen-home");
    refreshHomeScreen();
  });

  document.getElementById("quiz-options").addEventListener("click", (e) => {
    const letterBtn = e.target.closest(".option-letter");
    if (!letterBtn || letterBtn.disabled) return;
    if (reviewQueue) return; // gozden gecirme modunda secim yok
    currentQuiz.selectOption(Number(letterBtn.dataset.index));
  });

  document.getElementById("quiz-next").addEventListener("click", () => {
    if (reviewQueue) {
      reviewNext();
    } else {
      currentQuiz.next();
    }
  });

  document.getElementById("result-home-btn").addEventListener("click", () => {
    showScreen("screen-home");
    refreshHomeScreen();
  });
  document.getElementById("result-review-btn").addEventListener("click", startReviewOfWrong);
}

// ---------------------------------------------------------------------------
// Baslangic
// ---------------------------------------------------------------------------

async function init() {
  cacheEls();
  wireNav();
  wireVocabScreen();
  wireSettingsScreen();
  initDictionarySheet({ navigateToQuestion });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch((err) => console.error("SW kayit hatasi", err));
  }

  await loadIndex();
  await refreshHomeScreen();
  showScreen("screen-home");
}

init();
