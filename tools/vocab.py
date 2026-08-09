#!/usr/bin/env python3
"""
YDS kelime frekans hatti.

1) data/questions/*.json icindeki tum soru metinlerini (stem, passage,
   options) tarar, kelimeleri basit kurallarla lemmatize eder, en sik
   1000 Ingilizce kelimeyi (common_words.py) eleyip kalanlari frekansa
   gore data/vocab-frequency.json'a yazar.
2) ANTHROPIC_API_KEY ortam degiskeni varsa, en sik kelimelerden baslayarak
   Turkce karsilik + tur + ornek cumle uretip data/dictionary.json'a
   ekler (kaldigi yerden devam eder, API anahtari yoksa bu adim atlanir).

Kullanim:
    python tools/vocab.py                 # sadece frekans analizi
    python tools/vocab.py --dictionary     # frekans + (varsa API ile) sozluk
    python tools/vocab.py --dictionary --limit 300
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_words import COMMON_WORDS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_DIR = ROOT / "data" / "questions"
FREQ_PATH = ROOT / "data" / "vocab-frequency.json"
DICT_PATH = ROOT / "data" / "dictionary.json"

WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

IRREGULAR_LEMMAS = {
    "went": "go", "gone": "go", "goes": "go",
    "took": "take", "taken": "take",
    "found": "find", "given": "give", "gave": "give",
    "shown": "show", "showed": "show",
    "known": "know", "knew": "know",
    "grown": "grow", "grew": "grow", "fell": "fall", "fallen": "fall",
    "dealt": "deal", "dyed": "dye", "undergone": "undergo",
    "businessmen": "businessman", "hypotheses": "hypothesis",
    "computerised": "computerize",
    "written": "write", "wrote": "write",
    "spoken": "speak", "spoke": "speak",
    "broken": "break", "broke": "break",
    "chosen": "choose", "chose": "choose",
    "driven": "drive", "drove": "drive",
    "risen": "rise", "rose": "rise",
    "arisen": "arise", "arose": "arise",
    "began": "begin", "begun": "begin",
    "came": "come", "come": "come",
    "did": "do", "done": "do",
    "had": "have", "has": "have",
    "made": "make",
    "said": "say",
    "saw": "see", "seen": "see",
    "thought": "think",
    "brought": "bring",
    "bought": "buy",
    "caught": "catch",
    "taught": "teach",
    "sought": "seek",
    "held": "hold",
    "kept": "keep",
    "left": "leave",
    "meant": "mean",
    "met": "meet",
    "paid": "pay",
    "sold": "sell",
    "sent": "send",
    "told": "tell",
    "understood": "understand",
    "felt": "feel",
    "kept": "keep",
    "led": "lead",
    "lost": "lose",
    "built": "build",
    "spent": "spend",
    "stood": "stand",
    "won": "win",
    "children": "child",
    "men": "man",
    "women": "woman",
    "people": "person",
    "mice": "mouse",
    "feet": "foot",
    "teeth": "tooth",
    "better": "good",
    "best": "good",
    "worse": "bad",
    "worst": "bad",
    # silent-e ile biten fiillerin -ed hali (genel kurala uymaz, sik
    # gorulenler icin elle eslestirme)
    "used": "use", "hoped": "hope", "believed": "believe", "liked": "like",
    "lived": "live", "moved": "move", "closed": "close", "changed": "change",
    "decided": "decide", "provided": "provide", "required": "require",
    "produced": "produce", "reduced": "reduce", "created": "create",
    "involved": "involve", "continued": "continue", "increased": "increase",
    "examined": "examine", "imagined": "imagine", "achieved": "achieve",
    "described": "describe", "cared": "care", "shared": "share",
    "stored": "store", "noted": "note", "caused": "cause", "forced": "force",
    "placed": "place", "practiced": "practice", "practised": "practise",
    "arranged": "arrange", "managed": "manage", "encouraged": "encourage",
    "observed": "observe", "exposed": "expose", "combined": "combine",
    "determined": "determine", "guaranteed": "guarantee", "argued": "argue",
    "raised": "raise", "based": "base", "released": "release",
    "faced": "face", "traced": "trace", "forced": "force",
    "surprised": "surprise", "measured": "measure", "estimated": "estimate",
    "generated": "generate", "regulated": "regulate", "stimulated": "stimulate",
    "diagnosed": "diagnose", "exercised": "exercise", "recognized": "recognize",
    "recognised": "recognise", "organized": "organize", "organised": "organise",
    # silent-e ile biten fiillerin -ing hali
    "causing": "cause", "including": "include", "increasing": "increase",
    "comparing": "compare", "experiencing": "experience", "relating": "relate",
    "making": "make", "using": "use", "arguing": "argue", "arranging": "arrange",
    "managing": "manage", "encouraging": "encourage", "engaging": "engage",
    "changing": "change", "producing": "produce", "reducing": "reduce",
    "introducing": "introduce", "advancing": "advance", "forcing": "force",
    "placing": "place", "practicing": "practice", "noticing": "notice",
    "moving": "move", "solving": "solve", "improving": "improve",
    "achieving": "achieve", "believing": "believe", "receiving": "receive",
    "involving": "involve", "serving": "serve", "creating": "create",
    "indicating": "indicate", "estimating": "estimate", "communicating": "communicate",
    "educating": "educate", "demonstrating": "demonstrate", "operating": "operate",
    "regulating": "regulate", "stimulating": "stimulate", "generating": "generate",
    "translating": "translate", "recognizing": "recognize", "organizing": "organize",
    "emphasizing": "emphasize", "combining": "combine", "determining": "determine",
    "exposing": "expose", "raising": "raise", "basing": "base",
    "releasing": "release", "facing": "face", "tracing": "trace",
    "surprising": "surprise", "measuring": "measure", "diagnosing": "diagnose",
    "exercising": "exercise", "living": "live", "giving": "give", "having": "have",
    "leaving": "leave", "taking": "take", "coming": "come", "writing": "write",
    "driving": "drive", "riding": "ride", "hoping": "hope", "closing": "close",
    "deciding": "decide", "requiring": "require", "examining": "examine",
    "imagining": "imagine", "describing": "describe", "caring": "care",
    "sharing": "share", "storing": "store", "noting": "note",
    # bilesik isimler yanlislikla -ing gibi kirpilmasin (thing kelimesi
    # 'ing' ile bitiyor ama bir fiil degil)
    "something": "something", "anything": "anything", "everything": "everything",
    "nothing": "nothing",
    # tekil=cogul olan veya kuralin yanlis boldugu ozel kelimeler
    "species": "species", "series": "series",
    "diseased": "disease", "related": "relate",
    "called": "call", "always": "always", "thus": "thus",
    "mars": "mars",  # gezegen adi, 'mar' fiiliyle karismasin
    # -ying istisnalari (lie/die/tie -> ie ile biten fiiller, genel kural
    # bunlari 'try/cry' gibi -y ile biten fiillerle karistirir)
    "lying": "lie", "dying": "die", "tying": "tie", "vying": "vie",
    # silent-e ile biten ama listede eksik kalan -ed/-ing formlari
    "compared": "compare", "associated": "associate", "associating": "associate",
    "consumed": "consume", "consuming": "consume", "experienced": "experience",
    "perhaps": "perhaps",  # zarf, cogul degil ('perhap' diye bir kelime yok)
    # -us ile biten isimlerin cogulu (bu kelimeler '-use' fiil ailesiyle
    # (cause/excuse/abuse/refuse) karismasin diye ES kuralindan ayri, elle
    "focuses": "focus", "statuses": "status", "viruses": "virus",
    "bonuses": "bonus", "campuses": "campus", "geniuses": "genius",
    "emerged": "emerge", "emerging": "emerge",
    "stated": "state", "stating": "state",
    # 2013-2015 sozluk taramasinda bulunan silent-e kirpma hatalari
    # (raw kelime -> dogru sozluk anahtari; IRREGULAR_LEMMAS raw kelimeye
    # gore -ing/-ed kirpilmeden ONCE kontrol edildigi icin anahtar HAM kelime olmali)
    "accelerated": "accelerate", "accelerating": "accelerate", "activated": "activate",
    "activating": "activate", "admired": "admire", "advanced": "advance",
    "advertising": "advertise", "advised": "advise", "amazing": "amaze",
    "amputated": "amputate", "announced": "announce", "announcing": "announce",
    "appropriated": "appropriate", "arising": "arise", "aspiring": "aspire",
    "balanced": "balance", "becoming": "become", "behaved": "behave", "behaving": "behave",
    "blamed": "blame", "blaming": "blame", "challenged": "challenge",
    "challenging": "challenge", "characterized": "characterize", "choosing": "choose",
    "cloned": "clone", "cloning": "clone", "collapsed": "collapse",
    "concentrated": "concentrate", "concentrating": "concentrate", "confused": "confuse",
    "confusing": "confuse", "constituted": "constitute", "contaminated": "contaminate",
    "continuing": "continue", "contributed": "contribute", "contributing": "contribute",
    "convinced": "convince", "convincing": "convince", "coping": "cope", "cured": "cure",
    "damaged": "damage", "damaging": "damage", "debated": "debate", "debating": "debate",
    "decentralized": "decentralize", "declined": "decline", "declining": "decline",
    "dedicated": "dedicate", "dedicating": "dedicate", "defined": "define",
    "defining": "define", "demonstrated": "demonstrate", "deprived": "deprive",
    "depriving": "deprive", "derived": "derive", "deserved": "deserve", "devised": "devise",
    "devising": "devise", "disputed": "dispute", "educated": "educate",
    "eliminated": "eliminate", "eliminating": "eliminate", "embraced": "embrace",
    "enabled": "enable", "enabling": "enable", "engaged": "engage", "enhanced": "enhance",
    "enhancing": "enhance", "evaluated": "evaluate", "evaluating": "evaluate",
    "evolved": "evolve", "evolving": "evolve", "excited": "excite", "exciting": "excite",
    "executed": "execute", "executing": "execute", "exploring": "explore",
    "fascinated": "fascinate", "fascinating": "fascinate", "filled": "fill",
    "handled": "handle", "handling": "handle", "ignored": "ignore", "ignoring": "ignore",
    "improved": "improve", "included": "include", "incoming": "income", "induced": "induce",
    "injured": "injure", "integrated": "integrate", "integrating": "integrate",
    "intrigued": "intrigue", "intriguing": "intrigue", "introduced": "introduce",
    "investigated": "investigate", "investigating": "investigate", "invited": "invite",
    "inviting": "invite", "isolated": "isolate", "issued": "issue", "leisured": "leisure",
    "located": "locate", "losing": "lose", "loved": "love", "manipulated": "manipulate",
    "manipulating": "manipulate", "migrating": "migrate", "motivated": "motivate",
    "motivating": "motivate", "named": "name", "naming": "name", "observing": "observe",
    "operated": "operate", "opposed": "oppose", "overdiagnosed": "overdiagnose",
    "perceived": "perceive", "perceiving": "perceive", "pleased": "please",
    "pleasing": "please", "praised": "praise", "praising": "praise", "prepared": "prepare",
    "preparing": "prepare", "preserved": "preserve", "preserving": "preserve",
    "proved": "prove", "providing": "provide", "proving": "prove", "provoked": "provoke",
    "provoking": "provoke", "purchased": "purchase", "purchasing": "purchase",
    "ranging": "range", "realized": "realize", "realizing": "realize", "received": "receive",
    "recycled": "recycle", "recycling": "recycle", "removed": "remove", "removing": "remove",
    "replaced": "replace", "replacing": "replace", "reserved": "reserve",
    "restored": "restore", "rising": "rise", "ruled": "rule", "ruling": "rule",
    "saved": "save", "saving": "save", "separated": "separate", "settled": "settle",
    "settling": "settle", "shaking": "shake", "shaped": "shape", "shaping": "shape",
    "specialised": "specialise", "struggled": "struggle", "struggling": "struggle",
    "survived": "survive", "surviving": "survive", "traded": "trade", "trading": "trade",
    "welcomed": "welcome", "welcoming": "welcome",
    "assessed": "assess", "breed": "breed", "calling": "call", "chaos": "chaos",
    "complicated": "complicated", "deceased": "deceased", "depressed": "depress",
    "depressing": "depress", "diabetes": "diabetes", "discussed": "discuss",
    "discussing": "discuss", "expressed": "express", "expressing": "express",
    "hundred": "hundred", "inde": "indeed", "installed": "install", "installing": "install",
    "kissed": "kiss", "len": "lens", "obsessed": "obsess", "ongoing": "ongoing",
    "passed": "pass", "passing": "pass", "pulled": "pull", "pulling": "pull",
    "renowned": "renowned", "sel": "sell", "selling": "sell", "skilled": "skill",
    "sophisticated": "sophisticated", "speed": "speed", "spilled": "spill",
    "succeed": "succeed", "telling": "tell", "undereducated": "undereducated",
    "undeserved": "undeserved", "unemployed": "unemployed", "unexpected": "unexpected",
    "unlicensed": "unlicensed", "unlimited": "unlimited", "unprecedented": "unprecedented",
    "willing": "will", "witnessed": "witness", "witnessing": "witness",
    # 2. tur: 92.8% kapsamada bulunan ek silent-e kirpma hatalari
    "adhering": "adhere", "advocated": "advocate", "alienating": "alienate",
    "alternating": "alternate", "analyzes": "analyze", "analyzing": "analyze",
    "approved": "approve", "attributed": "attribute", "ceased": "cease",
    "celebrated": "celebrate", "celebrating": "celebrate", "centralized": "centralize",
    "confined": "confine", "criticizes": "criticize", "criticizing": "criticize",
    "cultivating": "cultivate", "deactivated": "deactivate", "deceiving": "deceive",
    "decomposing": "decompose", "decorated": "decorate", "enslaved": "enslave",
    "entitled": "entitle", "expired": "expire", "fantasized": "fantasize",
    "fluctuated": "fluctuate", "grappled": "grapple", "guiding": "guide",
    "imitating": "imitate", "incorporated": "incorporate", "industrialized": "industrialize",
    "initiated": "initiate", "institutionalized": "institutionalize",
    "intervening": "intervene", "intimidated": "intimidate", "jeopardizing": "jeopardize",
    "los": "lose", "mingling": "mingle", "miniaturized": "miniaturize",
    "minimizing": "minimize", "nursing": "nurse", "paved": "pave", "paving": "pave",
    "penalized": "penalize", "penetrating": "penetrate", "populated": "populate",
    "postponed": "postpone", "prioritized": "prioritize", "privileged": "privilege",
    "promising": "promise", "regenerating": "regenerate", "relieved": "relieve",
    "relieving": "relieve", "renovated": "renovate", "renovating": "renovate",
    "reshaping": "reshape", "retired": "retire", "revolutionizing": "revolutionize",
    "seized": "seize", "shelving": "shelve", "sneezing": "sneeze",
    "specialized": "specialize", "symbolizes": "symbolize", "underestimated": "underestimate",
    "undertaking": "undertake", "utilized": "utilize", "utilizes": "utilize",
}

ROMAN_NUMERAL_TOKENS = {
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii",
}


def lemmatize(word: str) -> str:
    w = word.lower()
    if w in IRREGULAR_LEMMAS:
        return IRREGULAR_LEMMAS[w]
    if len(w) <= 3:
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ied"):
        return w[:-3] + "y"
    if w.endswith("ing") and len(w) > 5:
        base = w[:-3]
        if len(base) >= 2 and base[-1] == base[-2] and base[-1] not in "aeiou":
            base = base[:-1]
        return base
    if w.endswith("es") and len(w) > 4:
        base = w[:-2]
        if base.endswith(("ss", "x", "z", "ch", "sh")):
            return base  # kisses->kiss, boxes->box, watches->watch
        if base.endswith("s"):
            return base + "e"  # causes->cause, cases->case, phases->phase
        return w[:-1]
    if w.endswith("ed") and len(w) > 4:
        base = w[:-2]
        if len(base) >= 2 and base[-1] == base[-2] and base[-1] not in "aeiou":
            base = base[:-1]
        return base
    if w.endswith("'s"):
        return w[:-2]
    if w.endswith("s") and not w.endswith(("ss", "us", "is")) and len(w) > 3:
        return w[:-1]
    return w


def collect_text_fields(question: dict) -> list[str]:
    """Sadece Ingilizce metin alanlarini toplar. Ceviri sorularinda
    (translation_en_tr / translation_tr_en) verilen cumle bir dilde,
    siklar diger dildedir; Turkce olan taraf kelime frekansina katilmaz."""
    fields = []
    q_type = question.get("type")
    if question.get("stem") and q_type != "translation_tr_en":
        fields.append(question["stem"])
    if question.get("passage"):
        fields.append(question["passage"])
    if q_type != "translation_en_tr":
        fields.extend(question.get("options") or [])
    return fields


def build_frequency() -> dict:
    entries: dict[str, dict] = {}
    files = sorted(QUESTIONS_DIR.glob("*.json"))
    if not files:
        print(f"UYARI: {QUESTIONS_DIR} icinde soru JSON'u bulunamadi. Once tools/parse.py calistir.")
        return {}

    for path in files:
        if path.name == "index.json":
            continue
        session_id = path.stem
        with open(path, encoding="utf-8") as f:
            questions = json.load(f)
        if not isinstance(questions, list):
            continue
        for q in questions:
            words_in_question = set()
            for text in collect_text_fields(q):
                for m in WORD_RE.finditer(text):
                    raw = m.group(0)
                    if "'" in raw:
                        raw = raw.split("'")[0]
                    if len(raw) < 3:
                        continue
                    if raw.lower() in ROMAN_NUMERAL_TOKENS:
                        continue
                    lemma = lemmatize(raw)
                    if lemma in COMMON_WORDS or raw.lower() in COMMON_WORDS:
                        continue
                    if not lemma.isalpha():
                        continue
                    words_in_question.add(lemma)
                    entry = entries.setdefault(lemma, {
                        "word": lemma,
                        "count": 0,
                        "sessions": set(),
                        "questionIds": set(),
                    })
                    entry["count"] += 1
                    entry["questionIds"].add(q["id"])
            for lemma in words_in_question:
                entries[lemma]["sessions"].add(session_id)

    result = []
    for lemma, e in entries.items():
        result.append({
            "word": lemma,
            "count": e["count"],
            "examCount": len(e["sessions"]),
            "questionIds": sorted(e["questionIds"]),
        })
    result.sort(key=lambda e: (-e["count"], e["word"]))
    return result


def write_frequency(freq_list: list[dict]) -> None:
    FREQ_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FREQ_PATH, "w", encoding="utf-8") as f:
        json.dump(freq_list, f, ensure_ascii=False, indent=2)
    print(f"-> {FREQ_PATH} ({len(freq_list)} kelime)")
    print("\nEn sik 20 kelime:")
    for e in freq_list[:20]:
        print(f"  {e['word']:20s} {e['count']:4d} kez, {e['examCount']} sinavda")


# ---------------------------------------------------------------------------
# Sozluk (API) asamasi
# ---------------------------------------------------------------------------

DICTIONARY_PROMPT = """Sen bir Ingilizce-Turkce sozluk asistanisin. Asagidaki Ingilizce kelime
icin YDS (Yabanci Dil Bilgisi Seviye Tespit Sinavi) hazirlanan bir ogrenciye
yonelik kisa bir sozluk kaydi olustur.

Kelime: "{word}"

Su JSON formatinda, SADECE JSON dondur (baska aciklama ekleme):
{{
  "translation": "en yaygin Turkce karsiligi (kisa)",
  "partOfSpeech": "noun|verb|adjective|adverb|other",
  "example": "kelimenin gectigi, YDS seviyesinde orta uzunlukta ornek Ingilizce cumle"
}}
"""


def call_anthropic(word: str, api_key: str, model: str) -> dict | None:
    import urllib.request

    body = json.dumps({
        "model": model,
        "max_tokens": 300,
        "messages": [{"role": "user", "content": DICTIONARY_PROMPT.format(word=word)}],
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  HATA (API): {word}: {e}")
        return None

    try:
        text = data["content"][0]["text"]
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(json)?", "", text).rsplit("```", 1)[0]
        return json.loads(text)
    except Exception as e:
        print(f"  HATA (parse): {word}: {e} -- raw: {data}")
        return None


def build_dictionary(freq_list: list[dict], limit: int | None) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\nANTHROPIC_API_KEY tanimli degil; sozluk adimi atlandi.")
        print("Sozluk uretmek icin: $env:ANTHROPIC_API_KEY='...'; python tools/vocab.py --dictionary")
        return

    model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")

    existing: dict = {}
    if DICT_PATH.exists():
        with open(DICT_PATH, encoding="utf-8") as f:
            existing = json.load(f)

    words = [e["word"] for e in freq_list]
    if limit:
        words = words[:limit]

    todo = [w for w in words if w not in existing]
    print(f"\nSozluk: {len(existing)} kelime zaten var, {len(todo)} kelime islenecek.")

    for i, word in enumerate(todo, 1):
        result = call_anthropic(word, api_key, model)
        if result is None:
            continue
        existing[word] = result
        print(f"  [{i}/{len(todo)}] {word} -> {result.get('translation')}")
        if i % 20 == 0:
            with open(DICT_PATH, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            print(f"    (ara kayit yapildi: {DICT_PATH})")
        time.sleep(0.3)

    with open(DICT_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"-> {DICT_PATH} ({len(existing)} kelime)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dictionary", action="store_true", help="API ile sozluk kaydi da uret")
    parser.add_argument("--limit", type=int, default=None, help="Sozluk icin islenecek kelime sayisi ustsiniri")
    args = parser.parse_args()

    freq_list = build_frequency()
    if not freq_list:
        sys.exit(1)
    write_frequency(freq_list)

    if args.dictionary:
        build_dictionary(freq_list, args.limit)


if __name__ == "__main__":
    main()
