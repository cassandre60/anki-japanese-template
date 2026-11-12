#!/usr/bin/env python3
"""Sample-deck fixture contract (ADR 007 / T18) + headless apkg builder checks.

The release apkg is built from repo files only (ADR 007):

  samples/fields.json   ordered note-type field names (derived by
                        fetch_sample_deck.py from the live collection —
                        the one committed field-list snapshot; tests
                        validate it against template references so it
                        can never silently drift)
  samples/notes.json    the sample deck's notes (guid, tags, fields)
  samples/media/        every media file referenced by those fields

Part 1 (fixtures) always runs. Part 2 (built apkg) checks
dist/anki-japanese-template.apkg produced by build_sample_apkg.py when it
exists, and is exercised end-to-end by `python3 build_sample_apkg.py
--check` wiring instead of requiring dist/ in a test run.

Run directly:  python3 tests/test_sample_apkg.py
Wired into ./verify. Stdlib only.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SAMPLES = os.path.join(ROOT, "samples")
MODEL_NAME = "Japanese Note type (Sentence card by Default)"

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name}" + (f" ({detail})" if detail and not cond else ""))
    if cond:
        PASS += 1
    else:
        FAIL += 1


def media_refs_in(value):
    refs = set()
    for match in re.findall(r"\[sound:([^\]]+)\]", value):
        refs.add(match.strip())
    for match in re.findall(r'<img[^>]*\ssrc=["\']([^"\']+)["\']', value, re.IGNORECASE):
        refs.add(match.strip())
    return {r for r in refs if r and not r.startswith(("data:", "http://", "https://")) and "/" not in r}


def main():
    fields_path = os.path.join(SAMPLES, "fields.json")
    notes_path = os.path.join(SAMPLES, "notes.json")
    media_dir = os.path.join(SAMPLES, "media")

    check("samples/fields.json exists", os.path.isfile(fields_path))
    check("samples/notes.json exists", os.path.isfile(notes_path))
    check("samples/media/ exists", os.path.isdir(media_dir))
    if FAIL:
        print(f"\n{PASS} passed, {FAIL} failed — run fetch_sample_deck.py first")
        return 1

    with open(fields_path, encoding="utf-8") as f:
        model_data = json.load(f)
    with open(notes_path, encoding="utf-8") as f:
        notes = json.load(f)

    check("fields.json records the product model name",
          isinstance(model_data, dict) and model_data.get("model") == MODEL_NAME)
    fields = model_data.get("fields") if isinstance(model_data, dict) else None
    check("field list is a non-empty list", isinstance(fields, list) and len(fields) >= 1)
    check("field list has no duplicates", isinstance(fields, list) and len(fields) == len(set(fields)))

    check("notes.json is a non-empty list", isinstance(notes, list) and len(notes) >= 1)
    if not (isinstance(notes, list) and notes):
        print(f"\n{PASS} passed, {FAIL} failed")
        return 1

    check("every note has a tags list", all(isinstance(n["tags"], list) for n in notes))
    check("every note has exactly the field-list fields",
          all(set(n["fields"]) == set(fields) for n in notes))
    check("notes sorted by Expression (deterministic fixtures)",
          [n["fields"]["Expression"] for n in notes]
          == sorted(n["fields"]["Expression"] for n in notes))

    referenced = set()
    for n in notes:
        for value in n["fields"].values():
            referenced |= media_refs_in(value)
    with open(os.path.join(SAMPLES, "media.json"), encoding="utf-8") as f:
        media_index = json.load(f)
    kept, dangling = set(media_index["files"]), set(media_index["missing"])
    check("media.json accounts for every referenced file (present or dangling)",
          referenced == kept | dangling,
          ", ".join(sorted(referenced ^ (kept | dangling))) or "ok")
    on_disk = set(os.listdir(media_dir))
    check("samples/media/ contains exactly the kept media files",
          on_disk == kept,
          ", ".join(sorted(on_disk ^ kept)) or "ok")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
