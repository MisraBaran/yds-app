// srs.js
// SM-2 turevi, sabit basamakli aralikli tekrar (spaced repetition) mantigi.
// Yanlis cevap -> basamak 0 (1 gun sonra). Dogru cevap -> bir sonraki
// basamaga ilerler: 1, 3, 7, 16, 35 gun. Dogru ama COK YAVAS cevaplanan
// sorular basamakta ilerletilmez (tekrar havuzunda kalir), boylece "biliyor
// gibi gorunen ama vakit kaybettiren" sorular da calisilmaya devam eder.

export const STEP_DAYS = [1, 3, 7, 16, 35];

export const SLOW_TIME_THRESHOLD_MS = {
  vocabulary: 30000,
  cloze: 40000,
  sentence_completion: 40000,
  translation_en_tr: 45000,
  translation_tr_en: 45000,
  reading: 70000,
  dialogue: 35000,
  restatement: 35000,
  paragraph_completion: 45000,
  irrelevant_sentence: 45000,
};

const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * @param {{step:number}} stat onceki durum ({step:0} yeni kayit icin uygun)
 * @param {boolean} isCorrect
 * @param {number|null} timeMs cevaplama suresi (ms)
 * @param {string} type soru tipi (yavaslik esigi icin)
 * @param {number} now Date.now()
 * @returns {{step:number, interval:number, nextDue:number, wasSlow:boolean}}
 */
export function nextSchedule(stat, isCorrect, timeMs, type, now = Date.now()) {
  const threshold = SLOW_TIME_THRESHOLD_MS[type] || 45000;
  const wasSlow = typeof timeMs === "number" && timeMs > threshold;

  let step = stat.step || 0;
  if (!isCorrect) {
    step = 0;
  } else if (wasSlow) {
    step = Math.max(0, step); // ilerletme, oldugu yerde kalsin
  } else {
    step = Math.min(step + 1, STEP_DAYS.length - 1);
  }
  const interval = STEP_DAYS[step];
  const nextDue = now + interval * DAY_MS;
  return { step, interval, nextDue, wasSlow };
}

export function isDue(stat, now = Date.now()) {
  return !!stat.nextDue && stat.nextDue <= now;
}
