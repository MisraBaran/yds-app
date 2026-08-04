#!/usr/bin/env python3
"""
YDS PDF ayristirici.

kaynak/ klasorundeki YDS soru kitapciklarini (Turkce ya da Ingilizce
yonergeli, 2013-2021 arasi ÖSYM formatlari) okuyup data/questions/ altina
JSON uretir. Cevap anahtari genellikle ayni PDF'in son sayfasinda gomulu
olarak gelir; ayri bir "-cevap.pdf" dosyasi varsa o da okunur.

Kullanim:
    python tools/parse.py                  # kaynak/ altindaki tum PDF'leri isler
    python tools/parse.py 2017-ilkbahar    # sadece tek bir dosyayi isler (uzantisiz ad)

Bagimlilik: pdfplumber (pip install pdfplumber)
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("HATA: pdfplumber kurulu degil. Once: pip install pdfplumber", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
KAYNAK_DIR = ROOT / "kaynak"
QUESTIONS_DIR = ROOT / "data" / "questions"
REVIEW_PATH = ROOT / "data" / "review-needed.json"

# ---------------------------------------------------------------------------
# Bilinen karakter / ligatur duzeltmeleri (font glyph -> gercek metin).
# ÖSYM kitapciklarinda bazi ozel ligaturler pdfminer tarafindan cid olarak
# gelir; burada gozlemlenen tum vakalar toplanir. Yeni bir tane bulunursa
# raporda "bilinmeyen cid" olarak gosterilir, sessizce atlanmaz.
# ---------------------------------------------------------------------------
CID_FIXES = {
    "(cid:129)": "tt",
    "(cid:257)": "tt",
}

# Sayfa filigranini (buyuk capraz "ÖSYM" harfleri) tanimlayan font/ olcek.
WATERMARK_FONT = "Helvetica"
WATERMARK_MIN_SIZE = 20

# Sayfa header/footer gibi tekrar eden, soru govdesine ait olmayan satirlar.
BOILERPLATE_PATTERNS = [
    re.compile(r"^\s*\d{1,3}\s+(Di[gğ]er sayfaya ge[cç]iniz\.?|Go on to the next page\.?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(Di[gğ]er sayfaya ge[cç]iniz\.?|Go on to the next page\.?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d{4}\s*[-.]?\s*YDS.*(?:[İI]NG[İI]L[İI]ZCE|ENGLISH).*$", re.IGNORECASE),
    re.compile(r"^\s*(TEST OF ENGLISH\s*){1,2}$", re.IGNORECASE),
    re.compile(r"^\s*(END OF THE TEST\.?|CHECK YOUR ANSWERS\.?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d{1,3}\s*$"),  # yalniz sayfa numarasindan olusan satir
]

ANCHOR_PATTERN = re.compile(
    r"(Bu testte 80 soru vard[ıi]r\.?|This test consists of 80 questions\.?)",
    re.IGNORECASE,
)

# "N. - M. sorularda ..." (TR) ve "N-M: ..." (EN) yonerge kaliplari.
RANGE_PATTERNS = [
    re.compile(
        r"(?P<start>\d{1,2})\s*\.\s*-\s*(?P<end>\d{1,2})\s*\.?\s*(?:sorular(?:da|ı)|sorusunu)"
        r"[,\s][\s\S]{0,220}?(?:bulunuz\.|cevaplay[ıi]n[ıi]z\.)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<start>\d{1,2})\s*-\s*(?P<end>\d{1,2})\s*:\s*[\s\S]{0,220}?"
        r"(?:passage\.|space\.|space\(s\)\.|spaces\.|sentence\.|sentences\.|dialogue\.|below\.|Turkish\.|English\.)",
        re.IGNORECASE,
    ),
]

TURKISH_CHARS = set("ışğçöüİĞÜŞÇÖı")


def normalize_for_match(text: str) -> str:
    t = text.lower()
    repl = {"ı": "i", "İ": "i", "ş": "s", "ğ": "g", "ç": "c", "ö": "o", "ü": "u"}
    for a, b in repl.items():
        t = t.replace(a, b)
    return t


# Yonerge metnine bakip soru tipini cikaran kural listesi (siraya bagli,
# en spesifik once). Hicbiri eslesmezse None donup review listesine dusuyor.
TYPE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"irrelevant|bozan c|butunlugunu bozan"), "irrelevant_sentence"),
    (re.compile(r"missing part of the|getirilebilecek c|complete the missing part"), "paragraph_completion"),
    (re.compile(r"rephrased form|anlamca en yakin c(?!.*(ingilizce|turkce))"), "restatement"),
    (re.compile(r"dialogue|karsilikli konusman"), "dialogue"),
    (re.compile(r"according to the passage|asagidaki parcaya gore|passage below"), "reading"),
    (re.compile(r"translation|en yakin turkce c|en yakin ingilizce c"), "translation"),
    (re.compile(r"complete the given sentence|tamamlayan ifadeyi|uygun sekilde tamamlayan"), "sentence_completion"),
    (re.compile(r"numaralanmis yerlere|numbered blank|spaces in the\s*passage"), "cloze"),
    (re.compile(r"fill the space|bos birakilan yerlere uygun dusen sozcuk"), "vocabulary"),
]


def classify_type(instruction_text: str) -> str | None:
    norm = normalize_for_match(instruction_text)
    norm = re.sub(r"\s+", " ", norm)
    for pattern, type_name in TYPE_RULES:
        if pattern.search(norm):
            return type_name
    return None


def turkish_ratio(text: str) -> float:
    if not text:
        return 0.0
    hits = sum(1 for ch in text if ch in TURKISH_CHARS)
    return hits / max(len(text), 1)


# ---------------------------------------------------------------------------
# PDF -> temiz metin
# ---------------------------------------------------------------------------

def _not_watermark(obj: dict) -> bool:
    if obj.get("object_type") != "char":
        return True
    if obj.get("fontname") == WATERMARK_FONT and (obj.get("size") or 0) > WATERMARK_MIN_SIZE:
        return False
    return True


def page_columns_text(page) -> str:
    """Filigrani temizleyip sayfayi sol/sag sutun olarak sirali okur."""
    clean = page.filter(_not_watermark)
    mid = page.width / 2
    left = clean.crop((0, 0, mid, page.height)).extract_text() or ""
    right = clean.crop((mid, 0, page.width, page.height)).extract_text() or ""
    return left + "\n" + right


def apply_cid_fixes(text: str) -> str:
    for cid, repl in CID_FIXES.items():
        text = text.replace(cid, repl)
    return text


PUA_ASCII_SHIFT = re.compile("[\uf020-\uf07e]")


def fix_pua_ascii(text: str) -> str:
    """Bazi kitapciklarda (ör. diyalog konusmaci ayraci "-") karakterler
    0xF000 kaydirmali Private Use Area kodlariyla gelir; ASCII karsiligina
    geri cevirir (ör. U+F02D -> '-')."""
    return PUA_ASCII_SHIFT.sub(lambda m: chr(ord(m.group(0)) - 0xF000), text)


def strip_boilerplate(text: str) -> str:
    lines = text.split("\n")
    kept = []
    for line in lines:
        if any(p.match(line) for p in BOILERPLATE_PATTERNS):
            continue
        kept.append(line)
    return "\n".join(kept)


def dehyphenate(text: str) -> str:
    # satir sonunda kelime kesmesi: "exam-\nple" -> "example"
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)


def find_unknown_cids(text: str) -> list[str]:
    return sorted(set(re.findall(r"\(cid:\d+\)", text)))


# ---------------------------------------------------------------------------
# Cevap anahtari
# ---------------------------------------------------------------------------

ANSWER_ENTRY = re.compile(r"(?<!\d)(\d{1,2})\s*\.\s*([A-E])\b(?!\w)")


def is_answer_key_page(text: str) -> bool:
    matches = ANSWER_ENTRY.findall(text)
    nums = {int(n) for n, _ in matches if 1 <= int(n) <= 80}
    return len(nums) >= 25


def extract_answer_key(pages_text: list[str]) -> dict[int, str]:
    answers: dict[int, str] = {}
    conflicts: list[str] = []
    for text in pages_text:
        for n_str, letter in ANSWER_ENTRY.findall(text):
            n = int(n_str)
            if not (1 <= n <= 80):
                continue
            if n in answers and answers[n] != letter:
                conflicts.append(f"{n}: {answers[n]} vs {letter}")
                continue
            answers[n] = letter
    if conflicts:
        print(f"  UYARI: cevap anahtarinda celisen kayitlar: {conflicts}")
    return answers


# ---------------------------------------------------------------------------
# Soru govdesi ayristirma
# ---------------------------------------------------------------------------

OPTION_MARKER = re.compile(r"([A-E])\)")
SEQ_NUMBER = re.compile(r"(?<![\d(])(\d{1,3})\s*\.\s")
# TR yonerge basliklarinda "17. - 21." gibi iki nokta iceren araliklar,
# SEQ_NUMBER ile karisir (her iki sayi da "digit + nokta" formuna uyar).
# Sirali numara taramasindan once bu baslik parcalarini maskeleriz.
RANGE_HEADER_MASK = re.compile(r"\d{1,2}\s*\.\s*-\s*\d{1,2}\s*\.")


@dataclass
class RangeInfo:
    start: int
    end: int
    type_: str | None
    instruction_raw: str
    header_start_pos: int  # yonerge metninin basladigi pozisyon
    block_end_pos: int  # yonerge metninin bittigi, govdenin basladigi pozisyon


def find_ranges(corpus: str) -> list[RangeInfo]:
    found = []
    for pattern in RANGE_PATTERNS:
        for m in pattern.finditer(corpus):
            start, end = int(m.group("start")), int(m.group("end"))
            if not (1 <= start <= end <= 80):
                continue
            if end - start > 40:
                continue
            found.append(
                RangeInfo(
                    start=start,
                    end=end,
                    type_=classify_type(m.group(0)),
                    instruction_raw=m.group(0).strip(),
                    header_start_pos=m.start(),
                    block_end_pos=m.end(),
                )
            )
    # ayni araligi birden fazla desen yakalamis olabilir; pozisyona gore
    # sirala ve start bazinda tekillestir (ilk gorulen kazanir).
    found.sort(key=lambda r: r.block_end_pos)
    seen_starts = set()
    unique = []
    for r in found:
        if r.start in seen_starts:
            continue
        seen_starts.add(r.start)
        unique.append(r)
    return unique


def find_sequential_numbers(corpus: str, max_n: int = 80) -> list[tuple[int, int]]:
    """Govde metninde 1..max_n sirali soru numaralarini bulur.
    Donen liste: (soru_no, metindeki_pozisyon:'.' dan hemen sonrasi)
    """
    masked = RANGE_HEADER_MASK.sub(lambda m: " " * len(m.group(0)), corpus)
    candidates = [(int(m.group(1)), m.end()) for m in SEQ_NUMBER.finditer(masked)]
    expected = 1
    accepted: list[tuple[int, int]] = []
    for n, pos in candidates:
        if n > max_n:
            continue
        if n == expected:
            accepted.append((n, pos))
            expected += 1
        elif expected < n <= expected + 3:
            # aradaki sayi(lar) kacirilmis olabilir, devam edelim.
            accepted.append((n, pos))
            expected = n + 1
        # n < expected ya da n > expected+3: govde metni icinde tesadufi
        # bir sayi (ör. "1990 yilinda 3. once") olabilir, atla.
    return accepted


def split_options(block: str) -> tuple[str, list[str]]:
    markers = list(OPTION_MARKER.finditer(block))
    if not markers:
        return block.strip(), []
    stem = block[: markers[0].start()].strip()
    # gecerli bir soru en fazla A-E (5) sik icerir; fazlasi govde tasmasi
    # gibi bir hataya isaret eder, sadece ilk 5'i sik olarak al.
    markers = markers[:5]
    options = []
    for i, m in enumerate(markers):
        end = markers[i + 1].start() if i + 1 < len(markers) else len(block)
        opt_text = block[m.end(): end].strip()
        opt_text = re.sub(r"\s+", " ", opt_text)
        options.append(opt_text)
    return stem, options


def clean_stem(stem: str) -> str:
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem


# ---------------------------------------------------------------------------
# Ana dosya isleme
# ---------------------------------------------------------------------------

FNAME_PATTERN = re.compile(r"^(\d{4})-([a-zA-Z]+|\d+)(?:-soru|-cevap)?$")


@dataclass
class FileReport:
    name: str
    year: int | None = None
    session: str | None = None
    total_extracted: int = 0
    complete_options: int = 0
    matched_answer: int = 0
    suspicious: list[dict] = field(default_factory=list)
    skipped_reason: str | None = None
    unknown_cids: list[str] = field(default_factory=list)
    missing_numbers: list[int] = field(default_factory=list)


def parse_year_session(stem_name: str) -> tuple[int | None, str | None]:
    m = FNAME_PATTERN.match(stem_name)
    if not m:
        return None, None
    return int(m.group(1)), m.group(2)


def process_pdf(path: Path, answer_key_path: Path | None = None) -> tuple[list[dict], FileReport]:
    stem_name = re.sub(r"-soru$", "", path.stem)
    year, session = parse_year_session(stem_name)
    report = FileReport(name=path.name, year=year, session=session)

    with pdfplumber.open(path) as pdf:
        page_texts = []
        for page in pdf.pages:
            page_texts.append(page_columns_text(page))

    if answer_key_path is not None:
        # ayri bir "-cevap.pdf" dosyasi var: cevap anahtarini oradan oku,
        # ana dosyanin tum sayfalari govde metni sayilir (kapak haric).
        with pdfplumber.open(answer_key_path) as pdf:
            answer_texts = [page_columns_text(page) for page in pdf.pages]
        body_texts = page_texts[1:]
    else:
        # cevap anahtari sayfalarini tespit et (genelde son 1-2 sayfa, ama
        # emin olmak icin tum dokumani tarayalim).
        answer_page_idx = {i for i, t in enumerate(page_texts) if is_answer_key_page(t)}
        answer_texts = [page_texts[i] for i in sorted(answer_page_idx)]
        body_texts = [t for i, t in enumerate(page_texts) if i not in answer_page_idx and i != 0]

    corpus_raw = "\n".join(body_texts)
    corpus = strip_boilerplate(corpus_raw)
    corpus = apply_cid_fixes(corpus)
    corpus = fix_pua_ascii(corpus)
    corpus = dehyphenate(corpus)

    unknown_cids = find_unknown_cids(corpus)
    report.unknown_cids = unknown_cids

    anchor = ANCHOR_PATTERN.search(corpus)
    if anchor:
        corpus = corpus[anchor.end():]
    else:
        report.suspicious.append({"reason": "Govde baslangic ipucu ('80 soru vardir') bulunamadi"})

    if not answer_texts:
        report.skipped_reason = "Cevap anahtari sayfasi bulunamadi (dosya atlandi)"
        return [], report

    answers = extract_answer_key(answer_texts)

    ranges = find_ranges(corpus)
    seq_numbers = find_sequential_numbers(corpus)
    seq_positions = {n: pos for n, pos in seq_numbers}

    found_nums = sorted(seq_positions.keys())
    missing = [n for n in range(1, 81) if n not in seq_positions]
    report.missing_numbers = missing

    def range_for(n: int) -> RangeInfo | None:
        for r in ranges:
            if r.start <= n <= r.end:
                return r
        return None

    # her aralik icin ortak passage'i bir kere hesapla (start pozisyonu ile
    # yonergenin bitis pozisyonu arasindaki metin).
    passage_cache: dict[tuple[int, int], str | None] = {}
    for r in ranges:
        key = (r.start, r.end)
        if r.start not in seq_positions:
            passage_cache[key] = None
            continue
        start_marker_pos = None
        # SEQ_NUMBER pozisyonu ".": sonrasidir; yonergeden hemen sonraki
        # gercek "start." isaretinin BASLANGICINI bulmak icin geri sar.
        m = re.search(r"(?<![\d(])" + str(r.start) + r"\s*\.\s", corpus[r.block_end_pos:])
        if not m:
            passage_cache[key] = None
            continue
        passage_candidate = corpus[r.block_end_pos: r.block_end_pos + m.start()].strip()
        passage_candidate = re.sub(r"\s+", " ", passage_candidate)
        passage_cache[key] = passage_candidate if len(passage_candidate) >= 40 else None

    # yonerge basi pozisyonlarinin sirali listesi: bir sorunun blogu, aradan
    # yeni bir aralik (ör. "43-46:") basliyorsa o baslikta durmali; aksi
    # halde bir sonraki aralik icin ortak passage de yanlislikla onceki
    # sorunun son sikkina eklenir.
    range_header_positions = sorted(r.header_start_pos for r in ranges)

    questions: list[dict] = []
    sorted_nums = found_nums
    for idx, n in enumerate(sorted_nums):
        start_pos = seq_positions[n]
        end_pos = seq_positions[sorted_nums[idx + 1]] if idx + 1 < len(sorted_nums) else len(corpus)
        # bir sonraki numaranin ONCESINDE "N. " isaretinin kendisi de var;
        # onu bloktan cikarmak icin bir onceki '.' baglaminda geri gitmeye
        # gerek yok, SEQ_NUMBER.end() zaten "N. " sonrasini verdigi icin
        # end_pos bir sonraki sayinin '.' SONRASI konumu -> bloğun sonuna
        # bir sonraki sayinin kendi metnini de katar. Bunu duzeltmek icin
        # bir sonraki "N+1." in basiligini bulup end_pos'u ona cekiyoruz.
        if idx + 1 < len(sorted_nums):
            next_n = sorted_nums[idx + 1]
            m2 = re.search(r"(?<![\d(])" + str(next_n) + r"\s*\.\s", corpus[start_pos:end_pos + 40])
            if m2:
                end_pos = start_pos + m2.start()
        # araya yeni bir aralik yonergesi giriyorsa (ör. Q42 sonrasinda
        # "43-46:" ve ardindan gelen ortak parca), bloğu orada kes; o metin
        # bir sonraki aralik grubuna ait, bu soruya degil.
        for hp in range_header_positions:
            if start_pos < hp < end_pos:
                end_pos = hp
                break
        block = corpus[start_pos:end_pos]
        stem, options = split_options(block)
        stem = clean_stem(stem)

        r = range_for(n)
        q_type = r.type_ if r else None
        passage = passage_cache.get((r.start, r.end)) if r else None
        group_id = f"{stem_name}-g{r.start}-{r.end}" if (r and passage) else None

        if q_type == "translation" and options:
            opts_joined = " ".join(options)
            q_type = "translation_en_tr" if turkish_ratio(opts_joined) > 0.01 else "translation_tr_en"

        answer_letter = answers.get(n)
        answer_idx = "ABCDE".index(answer_letter) if answer_letter else None

        qid = f"{stem_name}-q{n:02d}"
        question = {
            "id": qid,
            "source": {"year": year, "session": session, "number": n},
            "type": q_type,
            "groupId": group_id,
            "passage": passage,
            "stem": stem if stem else None,
            "options": options,
            "answer": answer_idx,
            "explanation": None,
            "vocab": [],
            "stats": {"seen": 0, "correct": 0, "lastSeen": None, "interval": 0, "ease": 2.5},
        }
        questions.append(question)

        issues = []
        if len(options) != 5 or any(not o for o in options):
            issues.append("5 sikkin tumu bulunamadi")
        if answer_idx is None:
            issues.append("cevap anahtarinda karsiligi yok")
        if q_type is None:
            issues.append("soru tipi yonergeden cikarilamadi")
        if not stem and q_type != "cloze":
            issues.append("soru koku bos")
        if issues:
            report.suspicious.append({"id": qid, "issues": issues})
        else:
            report.complete_options += 1
        if answer_idx is not None:
            report.matched_answer += 1

    report.total_extracted = len(questions)
    return questions, report


def write_report(reports: list[FileReport], all_review: list[dict]) -> None:
    print("\n" + "=" * 70)
    print("AYRISTIRMA RAPORU")
    print("=" * 70)
    for r in reports:
        print(f"\n[{r.name}]")
        if r.skipped_reason:
            print(f"  ATLANDI: {r.skipped_reason}")
            continue
        print(f"  Cikarilan soru: {r.total_extracted}/80")
        print(f"  5 sikki eksiksiz: {r.complete_options}")
        print(f"  Cevabi eslesen : {r.matched_answer}")
        print(f"  Suphe          : {len(r.suspicious)}")
        if r.missing_numbers:
            print(f"  Bulunamayan soru no: {r.missing_numbers}")
        if r.unknown_cids:
            print(f"  BILINMEYEN CID (elle kontrol et): {r.unknown_cids}")

    QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REVIEW_PATH, "w", encoding="utf-8") as f:
        json.dump(all_review, f, ensure_ascii=False, indent=2)
    print(f"\nSupheli kayitlar -> {REVIEW_PATH.relative_to(ROOT)} ({len(all_review)} kayit)")


def find_pdf_jobs(pdf_files: list[Path]) -> list[tuple[Path, Path | None, str]]:
    """kaynak/ klasorundeki PDF'leri isleme gorevlerine cevirir.
    Iki kalip desteklenir:
      - YIL-DONEM.pdf              (cevap anahtari ayni PDF icinde gomulu)
      - YIL-DONEM-soru.pdf + YIL-DONEM-cevap.pdf (ayri cevap anahtari PDF'i)
    Donen liste: (soru_pdf_yolu, cevap_pdf_yolu_veya_None, cikti_adi)
    """
    by_stem = {p.stem: p for p in pdf_files}
    jobs = []
    handled_cevap = set()
    for stem_name, path in by_stem.items():
        if stem_name.endswith("-cevap"):
            continue  # asagida esiyle birlikte islenecek
        if stem_name.endswith("-soru"):
            base = stem_name[: -len("-soru")]
            cevap_path = by_stem.get(f"{base}-cevap")
            if cevap_path:
                handled_cevap.add(cevap_path.stem)
                jobs.append((path, cevap_path, base))
            else:
                jobs.append((path, None, base))
        else:
            jobs.append((path, None, stem_name))
    return jobs


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if not KAYNAK_DIR.exists():
        print(f"HATA: {KAYNAK_DIR} bulunamadi.", file=sys.stderr)
        sys.exit(1)

    pdf_files = sorted(KAYNAK_DIR.glob("*.pdf"))
    jobs = find_pdf_jobs(pdf_files)
    if target:
        jobs = [j for j in jobs if j[2] == target]
        if not jobs:
            print(f"HATA: kaynak/{target}(.pdf | -soru.pdf) bulunamadi.", file=sys.stderr)
            sys.exit(1)

    reports = []
    all_review = []
    for soru_path, cevap_path, out_name in jobs:
        label = soru_path.name + (f" + {cevap_path.name}" if cevap_path else "")
        print(f"Isleniyor: {label}")
        questions, report = process_pdf(soru_path, answer_key_path=cevap_path)
        reports.append(report)
        if questions:
            out_path = QUESTIONS_DIR / f"{out_name}.json"
            QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(questions, f, ensure_ascii=False, indent=2)
            print(f"  -> {out_path.relative_to(ROOT)}")
        for item in report.suspicious:
            entry = dict(item)
            entry["file"] = label
            all_review.append(entry)

    write_report(reports, all_review)
    build_type_index()


def build_type_index() -> None:
    """Uygulamanin tip bazinda tembel yukleme yapabilmesi icin
    data/questions/*.json (oturum bazli) dosyalarini okuyup
    data/questions/by-type/{tip}.json (tum yillar birlesik) ve
    data/questions/index.json (ozet) uretir."""
    by_type: dict[str, list] = defaultdict(list)
    sessions_meta = []
    for path in sorted(QUESTIONS_DIR.glob("*.json")):
        if path.name == "index.json":
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            continue
        sessions_meta.append({"id": path.stem, "count": len(data)})
        for q in data:
            by_type[q.get("type") or "unknown"].append(q)

    by_type_dir = QUESTIONS_DIR / "by-type"
    by_type_dir.mkdir(parents=True, exist_ok=True)
    for t, qs in by_type.items():
        with open(by_type_dir / f"{t}.json", "w", encoding="utf-8") as f:
            json.dump(qs, f, ensure_ascii=False, indent=2)

    index = {
        "sessions": sessions_meta,
        "types": {t: len(qs) for t, qs in sorted(by_type.items())},
        "totalQuestions": sum(len(qs) for qs in by_type.values()),
    }
    with open(QUESTIONS_DIR / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"\nIndeks -> data/questions/index.json, data/questions/by-type/*.json ({len(by_type)} tip)")


if __name__ == "__main__":
    main()
