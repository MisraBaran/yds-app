// stats.js
// Puani asil yukselten kisim: performans analizi.
import { getState } from "./storage.js";

const TYPE_LABELS = {
  vocabulary: "Kelime/ifade tamamlama",
  cloze: "Cloze (parca) tamamlama",
  sentence_completion: "Cumle tamamlama",
  translation_en_tr: "Ceviri (ING->TR)",
  translation_tr_en: "Ceviri (TR->ING)",
  reading: "Okuma parcasi",
  dialogue: "Diyalog tamamlama",
  restatement: "Anlamca en yakin cumle",
  paragraph_completion: "Parca tamamlama",
  irrelevant_sentence: "Akisi bozan cumle",
};

export function typeLabel(type) {
  return TYPE_LABELS[type] || type || "Bilinmiyor";
}

export function accuracyByType() {
  const log = getState().answerLog;
  const byType = {};
  for (const entry of log) {
    const t = entry.type || "unknown";
    byType[t] = byType[t] || { seen: 0, correct: 0 };
    byType[t].seen += 1;
    if (entry.isCorrect) byType[t].correct += 1;
  }
  return Object.entries(byType)
    .map(([type, v]) => ({ type, seen: v.seen, correct: v.correct, rate: v.correct / v.seen }))
    .sort((a, b) => a.rate - b.rate);
}

export function avgTimeByType() {
  const log = getState().answerLog;
  const byType = {};
  for (const entry of log) {
    if (typeof entry.timeMs !== "number") continue;
    const t = entry.type || "unknown";
    byType[t] = byType[t] || { total: 0, count: 0 };
    byType[t].total += entry.timeMs;
    byType[t].count += 1;
  }
  return Object.entries(byType)
    .map(([type, v]) => ({ type, avgMs: v.total / v.count, count: v.count }))
    .sort((a, b) => b.avgMs - a.avgMs);
}

/** Zaman icindeki dogruluk: son N cevabi bucketSize'lik gruplara bolup
 * her grubun dogruluk oranini dondurur (basit hareketli ortalama grafigi). */
export function accuracyOverTime(bucketSize = 20) {
  const log = getState().answerLog;
  const buckets = [];
  for (let i = 0; i < log.length; i += bucketSize) {
    const slice = log.slice(i, i + bucketSize);
    const correct = slice.filter((e) => e.isCorrect).length;
    buckets.push({ index: buckets.length, rate: correct / slice.length, count: slice.length });
  }
  return buckets;
}

/**
 * En cok yanlis yapilan yapilar/kelimeler: yanlis cevaplanan sorularin
 * explanation.takeaway metinlerini gruplar. questionCache: Map<id, question>
 * (uygulama o ana kadar hangi sorulari fetch ettiyse onlari icerir).
 */
export function topMissedTakeaways(questionCache, limit = 10) {
  const log = getState().answerLog;
  const counts = new Map();
  for (const entry of log) {
    if (entry.isCorrect) continue;
    const q = questionCache.get(entry.questionId);
    const takeaway = q?.explanation?.takeaway;
    if (!takeaway) continue;
    counts.set(takeaway, (counts.get(takeaway) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([takeaway, count]) => ({ takeaway, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}

/** Bir "tam deneme" bitince: dogru sayisi * 1.25 = tahmini YDS puani (100 uzerinden). */
export function examScoreFromCorrectCount(correctCount, totalQuestions = 80) {
  const scaled = (correctCount / totalQuestions) * 100;
  return Math.round(scaled * 100) / 100;
}

/** Son 200 cevaba gore "su an sinava girsen" tahmini puan. */
export function estimatedCurrentScore() {
  const log = getState().answerLog;
  const recent = log.slice(-200);
  if (recent.length === 0) return null;
  const correct = recent.filter((e) => e.isCorrect).length;
  const rate = correct / recent.length;
  return Math.round(rate * 100 * 100) / 100;
}

export function weakestType() {
  const list = accuracyByType().filter((t) => t.seen >= 5);
  if (list.length === 0) return null;
  return list[0]; // en dusuk oranli (accuracyByType zaten artan sirali)
}

export function totalAnswered() {
  return getState().answerLog.length;
}
