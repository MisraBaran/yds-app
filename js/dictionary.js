// dictionary.js
// Metin icindeki her kelimeyi ayri <span class="w"> icine alir, dokununca
// alttan acilan sheet'te sozluk bilgisini gosterir. Sik secimiyle KESINLIKLE
// karismamasi icin: bu modul sadece metin govdelerine (stem/passage/option
// aciklama metni) uygulanir; sik secme dairesi ayri, kendi click handler'ina
// sahip bir dugmedir ve buraya hic dokunulmaz.
import { toggleSavedWord, isWordSaved } from "./storage.js";

let dictionaryData = null;
let vocabFrequency = null;
let vocabByWord = null;
let loadingPromise = null;

const WORD_RE = /[A-Za-z]+(?:'[A-Za-z]+)?/g;

const IRREGULAR_LEMMAS = {
  went: "go", gone: "go", goes: "go", took: "take", taken: "take",
  found: "find", given: "give", gave: "give", shown: "show", showed: "show",
  known: "know", knew: "know", grown: "grow", grew: "grow",
  written: "write", wrote: "write", spoken: "speak", spoke: "speak",
  broken: "break", broke: "break", chosen: "choose", chose: "choose",
  driven: "drive", drove: "drive", risen: "rise", rose: "rise",
  arisen: "arise", arose: "arise", began: "begin", begun: "begin",
  came: "come", did: "do", done: "do", had: "have", has: "have",
  made: "make", said: "say", saw: "see", seen: "see", thought: "think",
  brought: "bring", bought: "buy", caught: "catch", taught: "teach",
  sought: "seek", held: "hold", kept: "keep", left: "leave", meant: "mean",
  met: "meet", paid: "pay", sold: "sell", sent: "send", told: "tell",
  understood: "understand", felt: "feel", led: "lead", lost: "lose",
  built: "build", spent: "spend", stood: "stand", won: "win",
  children: "child", men: "man", women: "woman", people: "person",
  mice: "mouse", feet: "foot", teeth: "tooth", better: "good", best: "good",
  worse: "bad", worst: "bad", used: "use", hoped: "hope", believed: "believe",
  liked: "like", lived: "live", moved: "move", closed: "close",
  changed: "change", decided: "decide", provided: "provide",
  required: "require", produced: "produce", reduced: "reduce",
  created: "create", involved: "involve", continued: "continue",
  increased: "increase", examined: "examine", imagined: "imagine",
  achieved: "achieve", described: "describe",
  causing: "cause", including: "include", increasing: "increase",
  comparing: "compare", experiencing: "experience", relating: "relate",
  making: "make", using: "use", arguing: "argue", arranging: "arrange",
  managing: "manage", encouraging: "encourage", engaging: "engage",
  changing: "change", producing: "produce", reducing: "reduce",
  introducing: "introduce", advancing: "advance", forcing: "force",
  placing: "place", practicing: "practice", noticing: "notice",
  moving: "move", solving: "solve", improving: "improve",
  achieving: "achieve", believing: "believe", receiving: "receive",
  involving: "involve", serving: "serve", creating: "create",
  indicating: "indicate", estimating: "estimate", communicating: "communicate",
  educating: "educate", demonstrating: "demonstrate", operating: "operate",
  regulating: "regulate", stimulating: "stimulate", generating: "generate",
  translating: "translate", recognizing: "recognize", organizing: "organize",
  emphasizing: "emphasize", combining: "combine", determining: "determine",
  exposing: "expose", raising: "raise", basing: "base",
  releasing: "release", facing: "face", tracing: "trace",
  surprising: "surprise", measuring: "measure", diagnosing: "diagnose",
  exercising: "exercise", living: "live", giving: "give", having: "have",
  leaving: "leave", taking: "take", coming: "come", writing: "write",
  driving: "drive", riding: "ride", hoping: "hope", closing: "close",
  deciding: "decide", requiring: "require", examining: "examine",
  imagining: "imagine", describing: "describe", caring: "care",
  sharing: "share", storing: "store", noting: "note",
  something: "something", anything: "anything", everything: "everything",
  nothing: "nothing",
  species: "species", series: "series",
  diseased: "disease", related: "relate",
  called: "call", always: "always", thus: "thus",
  mars: "mars",
};

function lemmatize(raw) {
  const w = raw.toLowerCase();
  if (IRREGULAR_LEMMAS[w]) return IRREGULAR_LEMMAS[w];
  if (w.length <= 3) return w;
  if (w.endsWith("ies") && w.length > 4) return w.slice(0, -3) + "y";
  if (w.endsWith("ied")) return w.slice(0, -3) + "y";
  if (w.endsWith("ing") && w.length > 5) {
    let base = w.slice(0, -3);
    if (base.length >= 2 && base.at(-1) === base.at(-2) && !"aeiou".includes(base.at(-1))) {
      base = base.slice(0, -1);
    }
    return base;
  }
  if (w.endsWith("es") && w.length > 4) {
    const base = w.slice(0, -2);
    if (/(ss|x|z|ch|sh)$/.test(base)) return base;
    if (base.endsWith("s")) return base + "e";
    return w.slice(0, -1);
  }
  if (w.endsWith("ed") && w.length > 4) {
    let base = w.slice(0, -2);
    if (base.length >= 2 && base.at(-1) === base.at(-2) && !"aeiou".includes(base.at(-1))) {
      base = base.slice(0, -1);
    }
    return base;
  }
  if (w.endsWith("s") && !w.endsWith("ss") && w.length > 3) return w.slice(0, -1);
  return w;
}

async function ensureLoaded() {
  if (dictionaryData && vocabFrequency) return;
  if (loadingPromise) return loadingPromise;
  loadingPromise = Promise.all([
    fetch("data/dictionary.json").then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
    fetch("data/vocab-frequency.json").then((r) => (r.ok ? r.json() : [])).catch(() => []),
  ]).then(([dict, freq]) => {
    dictionaryData = dict;
    vocabFrequency = freq;
    vocabByWord = new Map(freq.map((e) => [e.word, e]));
  });
  return loadingPromise;
}

/** Bir DOM elemani icindeki duz metni kelime kelime <span class="w"> ile sarar. */
export function wrapWords(container) {
  if (!container || container.dataset.wordsWrapped === "1") return;
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
  const textNodes = [];
  let node;
  while ((node = walker.nextNode())) textNodes.push(node);

  for (const textNode of textNodes) {
    const text = textNode.nodeValue;
    if (!WORD_RE.test(text)) continue;
    WORD_RE.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let lastIndex = 0;
    let m;
    while ((m = WORD_RE.exec(text))) {
      if (m.index > lastIndex) {
        frag.appendChild(document.createTextNode(text.slice(lastIndex, m.index)));
      }
      const span = document.createElement("span");
      span.className = "w";
      span.textContent = m[0];
      span.dataset.word = lemmatize(m[0]);
      frag.appendChild(span);
      lastIndex = m.index + m[0].length;
    }
    if (lastIndex < text.length) {
      frag.appendChild(document.createTextNode(text.slice(lastIndex)));
    }
    textNode.parentNode.replaceChild(frag, textNode);
  }
  container.dataset.wordsWrapped = "1";
}

let sheetEl, sheetWordEl, sheetPosEl, sheetTranslationEl, sheetExampleEl, sheetExamCountEl, sheetLinksEl, sheetSaveBtn;
let currentWord = null;
let onNavigateToQuestion = null;

export function initDictionarySheet({ navigateToQuestion } = {}) {
  onNavigateToQuestion = navigateToQuestion || null;
  sheetEl = document.getElementById("word-sheet");
  sheetWordEl = document.getElementById("word-sheet-word");
  sheetPosEl = document.getElementById("word-sheet-pos");
  sheetTranslationEl = document.getElementById("word-sheet-translation");
  sheetExampleEl = document.getElementById("word-sheet-example");
  sheetExamCountEl = document.getElementById("word-sheet-exam-count");
  sheetLinksEl = document.getElementById("word-sheet-links");
  sheetSaveBtn = document.getElementById("word-sheet-save");

  document.body.addEventListener("click", (e) => {
    const span = e.target.closest(".w");
    if (span) {
      e.stopPropagation();
      openSheet(span.dataset.word);
      return;
    }
  });

  document.getElementById("word-sheet-backdrop").addEventListener("click", closeSheet);
  document.getElementById("word-sheet-handle").addEventListener("click", closeSheet);
  sheetSaveBtn.addEventListener("click", () => {
    if (!currentWord) return;
    const saved = toggleSavedWord(currentWord);
    sheetSaveBtn.textContent = saved ? "Kelimelerimde \u2713" : "Kelimelerime ekle";
    sheetSaveBtn.classList.toggle("is-saved", saved);
  });

  // asagi surukleyerek kapatma
  let startY = null;
  const sheetInner = document.getElementById("word-sheet-inner");
  sheetInner.addEventListener("touchstart", (e) => { startY = e.touches[0].clientY; }, { passive: true });
  sheetInner.addEventListener("touchmove", (e) => {
    if (startY == null) return;
    const dy = e.touches[0].clientY - startY;
    if (dy > 0) sheetInner.style.transform = `translateY(${dy}px)`;
  }, { passive: true });
  sheetInner.addEventListener("touchend", (e) => {
    if (startY == null) return;
    const dy = (e.changedTouches[0].clientY - startY);
    sheetInner.style.transform = "";
    if (dy > 80) closeSheet();
    startY = null;
  });
}

async function openSheet(word) {
  await ensureLoaded();
  currentWord = word;
  const entry = dictionaryData[word];
  const freq = vocabByWord ? vocabByWord.get(word) : null;

  sheetWordEl.textContent = word;
  sheetPosEl.textContent = entry?.partOfSpeech ? posLabel(entry.partOfSpeech) : "";
  sheetTranslationEl.textContent = entry?.translation || "Bu kelime icin henuz sozluk kaydi yok.";
  sheetExampleEl.textContent = entry?.example || "";
  sheetExampleEl.style.display = entry?.example ? "" : "none";

  if (freq) {
    sheetExamCountEl.textContent = `Bu kelime ${freq.examCount} sinavda cikti (toplam ${freq.count} kez).`;
    sheetLinksEl.innerHTML = "";
    freq.questionIds.slice(0, 8).forEach((qid) => {
      const a = document.createElement("button");
      a.className = "word-sheet-link";
      a.textContent = qid;
      a.addEventListener("click", () => {
        closeSheet();
        if (onNavigateToQuestion) onNavigateToQuestion(qid);
      });
      sheetLinksEl.appendChild(a);
    });
  } else {
    sheetExamCountEl.textContent = "";
    sheetLinksEl.innerHTML = "";
  }

  const saved = isWordSaved(word);
  sheetSaveBtn.textContent = saved ? "Kelimelerimde \u2713" : "Kelimelerime ekle";
  sheetSaveBtn.classList.toggle("is-saved", saved);

  sheetEl.classList.add("open");
  document.body.classList.add("sheet-open");
}

function closeSheet() {
  sheetEl.classList.remove("open");
  document.body.classList.remove("sheet-open");
  currentWord = null;
}

function posLabel(pos) {
  const map = { noun: "isim", verb: "fiil", adjective: "sifat", adverb: "zarf", other: "" };
  return map[pos] || pos;
}

export async function getVocabFrequency() {
  await ensureLoaded();
  return vocabFrequency;
}

export async function getDictionaryEntry(word) {
  await ensureLoaded();
  return dictionaryData[word] || null;
}
