// quiz.js
// Test akisi: soru gosterimi, sik secimi, aninda geri bildirim, sure
// takibi (soru basina, sure siniri yok), SRS'e sonuc bildirimi.
import { recordAnswer } from "./storage.js";
import { wrapWords } from "./dictionary.js";

const LETTERS = ["A", "B", "C", "D", "E"];

export class Quiz {
  /**
   * @param {object} opts
   * @param {Array} opts.questions
   * @param {(q:object,i:number,total:number)=>void} opts.onRender
   * @param {(result:object)=>void} opts.onAnswer her cevaptan sonra (aninda)
   * @param {(summary:object)=>void} opts.onFinish
   */
  constructor(opts) {
    this.questions = opts.questions;
    this.onRender = opts.onRender;
    this.onAnswer = opts.onAnswer;
    this.onFinish = opts.onFinish;

    this.index = 0;
    this.answers = new Array(this.questions.length).fill(null); // {selected, correct, timeMs}
    this.questionStartTs = null;
    this.quizStartTs = performance.now();
  }

  start() {
    this._renderCurrent();
  }

  get current() {
    return this.questions[this.index];
  }

  get total() {
    return this.questions.length;
  }

  _renderCurrent() {
    this.questionStartTs = performance.now();
    this.onRender(this.current, this.index, this.total);
  }

  /** Kullanici bir sik secti. index: 0-4. Sonuc aninda belli olur. */
  selectOption(optionIndex) {
    if (this.answers[this.index]) return null; // zaten cevaplanmis
    const q = this.current;
    const timeMs = Math.round(performance.now() - this.questionStartTs);
    const isCorrect = q.answer != null && optionIndex === q.answer;
    const result = { question: q, selected: optionIndex, isCorrect, timeMs, index: this.index };
    this.answers[this.index] = result;

    recordAnswer({ questionId: q.id, type: q.type, isCorrect, timeMs });

    this.onAnswer(result);
    return result;
  }

  hasNext() {
    return this.index < this.total - 1;
  }

  next() {
    if (!this.hasNext()) {
      this.finish();
      return;
    }
    this.index += 1;
    this._renderCurrent();
  }

  finish() {
    const answered = this.answers.filter(Boolean);
    const correctCount = answered.filter((a) => a.isCorrect).length;
    const totalTimeMs = Math.round(performance.now() - this.quizStartTs);
    const summary = {
      total: this.total,
      answered: answered.length,
      correct: correctCount,
      totalTimeMs,
      answers: this.answers,
    };
    this.onFinish(summary);
  }
}

/** Soru + siklari verilen konteynerlere basar, kelime sarma uygular. */
export function renderQuestionInto(question, els) {
  const { passageEl, stemEl, optionsEl } = els;

  delete passageEl.dataset.wordsWrapped;
  if (question.passage) {
    passageEl.textContent = question.passage;
    passageEl.hidden = false;
    wrapWords(passageEl);
  } else {
    passageEl.hidden = true;
    passageEl.textContent = "";
  }

  delete stemEl.dataset.wordsWrapped;
  stemEl.textContent = question.stem || "";
  wrapWords(stemEl);

  optionsEl.innerHTML = "";
  question.options.forEach((optText, i) => {
    const row = document.createElement("div");
    row.className = "option";
    row.dataset.index = String(i);

    const letterBtn = document.createElement("button");
    letterBtn.type = "button";
    letterBtn.className = "option-letter";
    letterBtn.dataset.index = String(i);
    letterBtn.textContent = LETTERS[i];
    letterBtn.setAttribute("aria-label", `Sik ${LETTERS[i]}`);

    const textEl = document.createElement("div");
    textEl.className = "option-text";
    textEl.textContent = optText;

    row.appendChild(letterBtn);
    row.appendChild(textEl);
    optionsEl.appendChild(row);
    wrapWords(textEl);
  });
}

export function markOptionResult(optionsEl, { selected, correctIndex }) {
  const rows = optionsEl.querySelectorAll(".option");
  rows.forEach((row) => {
    const i = Number(row.dataset.index);
    row.classList.remove("is-correct", "is-wrong", "is-selected");
    row.querySelector(".option-tag")?.remove();

    const isSelected = i === selected;
    const isCorrect = i === correctIndex;
    if (isCorrect) row.classList.add("is-correct");
    if (isSelected && !isCorrect) row.classList.add("is-wrong");
    if (isSelected) row.classList.add("is-selected");

    // renk korlugu olan/olmayan herkes icin metinle de netlestir: hangisini
    // isaretledigin ve dogru cevap hangisiydi ac ac yazilir.
    if (isSelected || isCorrect) {
      const tag = document.createElement("span");
      tag.className = "option-tag";
      if (isSelected && isCorrect) tag.textContent = "Senin cevabin \u2713 dogru";
      else if (isSelected) tag.textContent = "Senin cevabin \u2717";
      else tag.textContent = "Dogru cevap";
      row.appendChild(tag);
    }

    row.querySelector(".option-letter").disabled = true;
  });
}

export function formatExplanation(question, selected) {
  const exp = question.explanation;
  if (!exp) {
    return { correct: "Bu soru icin henuz aciklama uretilmedi.", distractorText: "", takeaway: "", hint: "" };
  }
  const distractorText =
    selected != null && selected !== question.answer && exp.distractors
      ? exp.distractors[String(selected)] || ""
      : "";
  return {
    correct: exp.correct || "",
    distractorText,
    takeaway: exp.takeaway || "",
    hint: exp.hint || "",
  };
}

export function formatTime(ms) {
  const totalSec = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
