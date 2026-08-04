// storage.js
// Tum ilerleme localStorage'da tutulur. Tek kaynak: STORAGE_KEY altindaki
// tek bir JSON blobu. iOS zaman zaman site verisini temizleyebildigi icin
// disa/ice aktarma (export/import) burada saglanir.
import { nextSchedule } from "./srs.js";

const STORAGE_KEY = "yds-app-state-v1";
const SCHEMA_VERSION = 1;

function defaultState() {
  return {
    version: SCHEMA_VERSION,
    createdAt: Date.now(),
    // soruId -> { type, seen, correct, lastSeen, interval, step, ease, lastTimeMs }
    questionStats: {},
    // kaydedilen (aralikli tekrara giren) kelimeler: word -> { addedAt }
    savedWords: {},
    // word -> { seen, correct, lastSeen, interval, step }
    wordStats: {},
    // son cevaplarin gunlugu (istatistik icin), en fazla ~1000 kayit tutulur
    answerLog: [],
    // tamamlanan deneme/oturum ozetleri
    sessions: [],
    settings: {
      reduceMotion: false,
    },
  };
}

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultState();
    const parsed = JSON.parse(raw);
    return { ...defaultState(), ...parsed };
  } catch (e) {
    console.error("storage.load basarisiz, sifirlaniyor", e);
    return defaultState();
  }
}

let state = load();
const listeners = new Set();

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (e) {
    console.error("storage.persist basarisiz (kota dolu olabilir)", e);
  }
  listeners.forEach((fn) => {
    try {
      fn(state);
    } catch (_) {
      /* noop */
    }
  });
}

export function getState() {
  return state;
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function getQuestionStat(id) {
  return (
    state.questionStats[id] || {
      type: null,
      seen: 0,
      correct: 0,
      lastSeen: null,
      interval: 0,
      step: 0,
      ease: 2.5,
      lastTimeMs: null,
    }
  );
}

export function recordAnswer({ questionId, type, isCorrect, timeMs }) {
  const stat = getQuestionStat(questionId);
  stat.type = type;
  stat.seen += 1;
  stat.lastSeen = Date.now();
  stat.lastTimeMs = timeMs ?? null;
  if (isCorrect) stat.correct += 1;

  const sched = nextSchedule(stat, isCorrect, timeMs, type);
  stat.step = sched.step;
  stat.interval = sched.interval;
  stat.nextDue = sched.nextDue;

  state.questionStats[questionId] = stat;

  state.answerLog.push({
    questionId,
    type,
    isCorrect,
    timeMs: timeMs ?? null,
    ts: Date.now(),
  });
  if (state.answerLog.length > 1000) {
    state.answerLog = state.answerLog.slice(-1000);
  }

  persist();
  return stat;
}

export function getDueQuestionIds(now = Date.now()) {
  return Object.entries(state.questionStats)
    .filter(([, s]) => s.nextDue && s.nextDue <= now)
    .map(([id]) => id);
}

export function getWrongQuestionIds() {
  return Object.entries(state.questionStats)
    .filter(([, s]) => s.seen > 0 && s.correct < s.seen)
    .map(([id]) => id);
}

export function toggleSavedWord(word) {
  if (state.savedWords[word]) {
    delete state.savedWords[word];
  } else {
    state.savedWords[word] = { addedAt: Date.now() };
  }
  persist();
  return !!state.savedWords[word];
}

export function isWordSaved(word) {
  return !!state.savedWords[word];
}

export function recordWordAnswer(word, isCorrect) {
  const s = state.wordStats[word] || { seen: 0, correct: 0, lastSeen: null, interval: 0, step: 0 };
  s.seen += 1;
  if (isCorrect) s.correct += 1;
  s.lastSeen = Date.now();
  const sched = nextSchedule(s, isCorrect, null, "vocabulary");
  s.step = sched.step;
  s.interval = sched.interval;
  s.nextDue = sched.nextDue;
  state.wordStats[word] = s;
  persist();
  return s;
}

export function getDueWords(now = Date.now()) {
  return Object.entries(state.wordStats)
    .filter(([, s]) => s.nextDue && s.nextDue <= now)
    .map(([w]) => w);
}

export function recordSessionSummary(summary) {
  state.sessions.push({ ...summary, ts: Date.now() });
  if (state.sessions.length > 200) state.sessions = state.sessions.slice(-200);
  persist();
}

export function exportStateAsJSON() {
  return JSON.stringify(state, null, 2);
}

export function importStateFromJSON(text) {
  const parsed = JSON.parse(text);
  state = { ...defaultState(), ...parsed };
  persist();
}

export function resetAllProgress() {
  state = defaultState();
  persist();
}

export function updateSettings(patch) {
  state.settings = { ...state.settings, ...patch };
  persist();
}
