#!/usr/bin/env python3
"""
Cikmis YDS sorulari icin Turkce aciklama uretir (Anthropic API).

Tek seferlik, toplu calisir; sonuc her sorunun JSON dosyasina "explanation"
alani olarak gomulur, boylece uygulama daha sonra tamamen cevrimdisi ve
API'siz calisabilir. Zaten "explanation" dolu olan sorular atlanir, yani
script kesintiye ugrarsa kaldigi yerden devam eder.

Kullanim:
    $env:ANTHROPIC_API_KEY = "sk-ant-..."
    python tools/explain.py                  # tum data/questions/*.json
    python tools/explain.py 2019-1            # tek dosya
    python tools/explain.py --limit 50        # sadece ilk 50 soru (test icin)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_DIR = ROOT / "data" / "questions"

LETTERS = "ABCDE"

PROMPT_TEMPLATE = """Sen deneyimli bir YDS (Yabanci Dil Bilgisi Seviye Tespit Sinavi)
Ingilizce ogretmenisin. Asagidaki cikmis soruyu, sinava hazirlanan bir
ogrenciye TAMAMEN TURKCE olarak aciklayacaksin.

{passage_block}Soru koku: {stem}

Siklar:
{options_block}

Dogru cevap: {correct_letter}) {correct_text}

Gorevin, SADECE asagidaki JSON semasina uyan bir cevap uretmek (baska hicbir
metin ekleme, aciklama yapma, kod bloguyla sarmalama):

{{
  "correct": "Dogru cevabin neden dogru oldugunu aciklayan 1-3 cumle. Hangi
    ipucu, hangi dilbilgisi yapisi, hangi essiz-anlam (collocation) bu cevabi
    zorunlu kiliyor, somut olarak belirt.",
  "distractors": {{
    "{d0}": "{d0} sikkinin neden yanlis oldugunu aciklayan 1 cumle.",
    "{d1}": "{d1} sikkinin neden yanlis oldugunu aciklayan 1 cumle.",
    "{d2}": "{d2} sikkinin neden yanlis oldugunu aciklayan 1 cumle.",
    "{d3}": "{d3} sikkinin neden yanlis oldugunu aciklayan 1 cumle."
  }},
  "takeaway": "Bu sorudan akilda kalmasi gereken TEK cumlelik kural veya kalip."
}}

ONEMLI KURALLAR:
- Her celdiriciyi TEK TEK, kendine ozgu bir gerekceyle acikla. "Digerleri
  anlamsiz", "baglama uymuyor" gibi genel gecer, gecistirici ifadeler
  KESINLIKLE YASAK. Her sikkin kendi anlami/yapisi neden bu cumleye
  uymuyor, somut olarak yaz.
- distractors objesindeki anahtarlar SADECE yanlis siklarin index'leri
  olmali (dogru cevabin index'i orada OLMAMALI).
- Cikti GECERLI JSON olmali, ekstra metin icermemeli.
"""


def format_options_block(options: list[str]) -> str:
    return "\n".join(f"{LETTERS[i]}) {opt}" for i, opt in enumerate(options))


def build_prompt(q: dict) -> str | None:
    options = q.get("options") or []
    answer = q.get("answer")
    if answer is None or len(options) != 5:
        return None
    distractor_indices = [i for i in range(5) if i != answer]
    passage_block = f"Parca: {q['passage']}\n\n" if q.get("passage") else ""
    stem = q.get("stem") or "(bu soru tipinde ayri bir soru koku yoktur, siklara bakiniz)"
    return PROMPT_TEMPLATE.format(
        passage_block=passage_block,
        stem=stem,
        options_block=format_options_block(options),
        correct_letter=LETTERS[answer],
        correct_text=options[answer],
        d0=distractor_indices[0],
        d1=distractor_indices[1],
        d2=distractor_indices[2],
        d3=distractor_indices[3],
    )


def call_anthropic(prompt: str, api_key: str, model: str) -> dict | None:
    body = json.dumps({
        "model": model,
        "max_tokens": 900,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    HATA (API cagrisi): {e}")
        return None

    try:
        text = data["content"][0]["text"].strip()
        if text.startswith("```"):
            text = re.sub(r"^```(json)?", "", text).rsplit("```", 1)[0]
        parsed = json.loads(text)
    except Exception as e:
        print(f"    HATA (JSON parse): {e} -- raw: {str(data)[:300]}")
        return None

    if "correct" not in parsed or "distractors" not in parsed or "takeaway" not in parsed:
        print(f"    HATA: beklenen alanlar eksik: {parsed}")
        return None
    return parsed


def process_file(path: Path, api_key: str, model: str, limit: int | None, delay: float) -> tuple[int, int]:
    with open(path, encoding="utf-8") as f:
        questions = json.load(f)

    done = 0
    skipped_no_answer = 0
    processed_this_run = 0
    changed = False

    for q in questions:
        if q.get("explanation"):
            done += 1
            continue
        if limit is not None and processed_this_run >= limit:
            break
        prompt = build_prompt(q)
        if prompt is None:
            skipped_no_answer += 1
            continue

        print(f"  {q['id']} ...", end=" ", flush=True)
        result = call_anthropic(prompt, api_key, model)
        processed_this_run += 1
        if result is None:
            print("basarisiz, atlandi")
            continue
        q["explanation"] = result
        changed = True
        done += 1
        print("tamam")

        if processed_this_run % 10 == 0:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(questions, f, ensure_ascii=False, indent=2)
        time.sleep(delay)

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)

    return done, len(questions)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", help="tek bir dosya adi (uzantisiz), yoksa tumu")
    parser.add_argument("--limit", type=int, default=None, help="bu calistirmada islenecek soru sayisi ustsiniri (test icin)")
    parser.add_argument("--delay", type=float, default=0.5, help="API cagrilari arasi bekleme (sn)")
    parser.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"))
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("HATA: ANTHROPIC_API_KEY ortam degiskeni tanimli degil.", file=sys.stderr)
        print("  PowerShell: $env:ANTHROPIC_API_KEY = 'sk-ant-...'", file=sys.stderr)
        sys.exit(1)

    files = sorted(p for p in QUESTIONS_DIR.glob("*.json") if p.name != "index.json")
    if args.target:
        files = [p for p in files if p.stem == args.target]
        if not files:
            print(f"HATA: data/questions/{args.target}.json bulunamadi.", file=sys.stderr)
            sys.exit(1)

    total_done = total_all = 0
    for path in files:
        print(f"\n{path.name}")
        done, all_ = process_file(path, api_key, args.model, args.limit, args.delay)
        total_done += done
        total_all += all_
        print(f"  -> {done}/{all_} aciklamali")

    print(f"\nTOPLAM: {total_done}/{total_all} soru aciklamali.")


if __name__ == "__main__":
    main()
