#!/usr/bin/env python3
"""
Bir JSON dosyasindaki {questionId: {hint, correct, distractors, takeaway}}
eslemelerini ilgili data/questions/{session}.json dosyalarina isler.

Kullanim:
    python tools/merge_explanations.py path/to/batch.json
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_DIR = ROOT / "data" / "questions"


def session_id_from_qid(qid: str) -> str:
    return qid.rsplit("-q", 1)[0]


def main():
    if len(sys.argv) < 2:
        print("Kullanim: python tools/merge_explanations.py batch.json", file=sys.stderr)
        sys.exit(1)

    batch_path = Path(sys.argv[1])
    with open(batch_path, encoding="utf-8") as f:
        batch = json.load(f)

    by_session = defaultdict(dict)
    for qid, exp in batch.items():
        by_session[session_id_from_qid(qid)][qid] = exp

    total_updated = 0
    for session_id, entries in by_session.items():
        path = QUESTIONS_DIR / f"{session_id}.json"
        if not path.exists():
            print(f"UYARI: {path} bulunamadi, atlandi")
            continue
        with open(path, encoding="utf-8") as f:
            questions = json.load(f)
        updated = 0
        for q in questions:
            if q["id"] in entries:
                q["explanation"] = entries[q["id"]]
                updated += 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        print(f"{session_id}.json -> {updated} soru guncellendi")
        total_updated += updated

    print(f"\nTOPLAM: {total_updated} soru guncellendi")


if __name__ == "__main__":
    main()
