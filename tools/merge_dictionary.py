#!/usr/bin/env python3
"""
Bir JSON dosyasindaki {kelime: {translation, partOfSpeech, example}}
eslemelerini data/dictionary.json icine isler (var olanlarin uzerine yazar,
digerlerini korur).

Kullanim:
    python tools/merge_dictionary.py path/to/batch.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DICT_PATH = ROOT / "data" / "dictionary.json"


def main():
    if len(sys.argv) < 2:
        print("Kullanim: python tools/merge_dictionary.py batch.json", file=sys.stderr)
        sys.exit(1)

    batch_path = Path(sys.argv[1])
    with open(batch_path, encoding="utf-8") as f:
        batch = json.load(f)

    existing = {}
    if DICT_PATH.exists():
        with open(DICT_PATH, encoding="utf-8") as f:
            existing = json.load(f)

    existing.update(batch)

    with open(DICT_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"{len(batch)} kelime eklendi/guncellendi. Toplam: {len(existing)} kelime.")


if __name__ == "__main__":
    main()
