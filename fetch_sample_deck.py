#!/usr/bin/env python3
"""Derive the release sample-deck fixtures from the live Anki collection.

fetch_sample_deck.py (ADR 007 / T18): the release apkg is built by
build_sample_apkg.py from repo files only; this script is the ONLY writer
of those files. It derives (never hand-edits):

  samples/fields.json   note-type field snapshot (names + font/size/
                        description) of the note type (modelFieldNames/
                        modelFieldFonts/modelFieldDescriptions)
  samples/notes.json    the sample deck's notes: tags, fields by name
  samples/media/        every media file referenced by those fields

Run only when the maintainer wants to refresh the shipped sample deck;
Anki must be running with Anki-Connect. Output is deterministic: notes
sorted by guid, media sorted by filename, JSON indented with stable key
order. Notes are resolved through the deck's CARDS (findCards → cardsInfo),
so the shipped content always matches exactly what the deck exports.
"""

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request

ANKI_CONNECT_URL = "http://127.0.0.1:8765"
DECK_NAME = "My Life Decks::Japanese::anki-japanese-template"
MODEL_NAME = "Japanese Note type (Sentence card by Default)"
SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
MEDIA_DIR = os.path.join(SAMPLES_DIR, "media")


# The deck name contains hyphens; Anki's search lexer reads bare hyphens as
# negation (observed: an escaped query is required, otherwise 0 results).
def deck_query(deck: str) -> str:
    return 'deck:"' + deck.replace("-", r"\-") + '"'


def post(action: str, params: dict):
    payload = {"action": action, "version": 6, "params": params}
    req = urllib.request.Request(
        ANKI_CONNECT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError:
        sys.exit("ERROR: cannot reach Anki-Connect (is Anki running with the add-on?)")
    if result.get("error"):
        sys.exit(f"ERROR: Anki-Connect {action} failed: {result['error']}")
    return result["result"]


def media_refs_in(field_value: str):
    """Every collection-media filename referenced by one field value."""
    refs = set()
    for match in re.findall(r"\[sound:([^\]]+)\]", field_value):
        refs.add(match.strip())
    for match in re.findall(
        r'<img[^>]*\ssrc=["\']([^"\']+)["\']', field_value, re.IGNORECASE
    ):
        refs.add(match.strip())
    # Media references are bare filenames inside collection.media; skip
    # inline data URIs and remote URLs (nothing to fetch).
    return {
        r
        for r in refs
        if r and not r.startswith(("data:", "http://", "https://")) and "/" not in r
    }


def main() -> int:
    card_ids = post("findCards", {"query": deck_query(DECK_NAME)})
    if not card_ids:
        sys.exit(f"ERROR: deck has no cards: {DECK_NAME}")
    cards = post("cardsInfo", {"cards": card_ids})
    note_ids = sorted({card["note"] for card in cards})
    notes_raw = post("notesInfo", {"notes": note_ids})

    models = {info["modelName"] for info in notes_raw}
    if models != {MODEL_NAME}:
        sys.exit(f"ERROR: unexpected note type(s) in sample deck: {sorted(models)}")
    field_names = post("modelFieldNames", {"modelName": MODEL_NAME})
    # Per-field metadata the builder needs to compose the note type faithfully
    # (without it the release would ship default fonts and empty descriptions).
    # sticky/rtl/plainText are NOT exposed by this Anki-Connect build; the live
    # model's dumped JSON shows sticky=false and rtl=false for all fields, so
    # build_sample_apkg.py composes those as false (documented limitation).
    fonts = post("modelFieldFonts", {"modelName": MODEL_NAME})  # {name: {font, size}}
    descriptions = post("modelFieldDescriptions", {"modelName": MODEL_NAME})
    if len(descriptions) != len(field_names):
        sys.exit("ERROR: description list does not match the field list")
    fields_meta = [
        {
            "name": name,
            "font": fonts[name]["font"],
            "size": fonts[name]["size"],
            "description": descriptions[index],
        }
        for index, name in enumerate(field_names)
    ]

    notes = []
    refs = set()
    for info in notes_raw:
        fields = {
            name: (value["value"] if isinstance(value, dict) else value)
            for name, value in info["fields"].items()
        }
        if set(fields) != set(field_names):
            sys.exit(
                f"ERROR: note {info['noteId']} fields do not match the model's field list"
            )
        for value in fields.values():
            refs |= media_refs_in(value)
        tags_raw = info["tags"]
        tags = tags_raw if isinstance(tags_raw, list) else tags_raw.split()
        notes.append(
            {
                "tags": tags,
                "fields": fields,
            }
        )
    # guids are NOT derived here: this Anki-Connect build does not expose
    # them, and repo-derived fixtures should not depend on live-collection
    # internals anyway. build_sample_apkg.py assigns deterministic
    # content-hash guids so re-importing a newer release updates instead
    # of duplicating.
    notes.sort(key=lambda n: n["fields"]["Expression"])

    os.makedirs(MEDIA_DIR, exist_ok=True)
    fetched, missing = [], []
    for name in sorted(refs):
        target = os.path.join(MEDIA_DIR, name)
        if os.path.isfile(target) and os.path.getsize(target) > 0:
            fetched.append(name)
            continue  # already derived; keep bytes identical
        b64 = post("retrieveMediaFile", {"filename": name})
        if not b64:
            # Dangling reference: the field cites media that is no longer in
            # collection.media. Anki's own exporter skips these too; record
            # instead of failing so the fixtures mirror the live deck.
            missing.append(name)
            print(f"WARN: media not in collection.media (dangling ref): {name}")
            continue
        with open(target, "wb") as f:
            f.write(base64.b64decode(b64))
        fetched.append(name)
    fetched.sort()
    missing.sort()

    with open(os.path.join(SAMPLES_DIR, "media.json"), "w", encoding="utf-8") as f:
        json.dump(
            {"files": fetched, "missing": missing}, f, ensure_ascii=False, indent=2
        )
        f.write("\n")

    model = {
        "model": MODEL_NAME,
        "fields": fields_meta,
    }
    with open(os.path.join(SAMPLES_DIR, "fields.json"), "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(os.path.join(SAMPLES_DIR, "notes.json"), "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)
        f.write("\n")

    total = sum(
        os.path.getsize(os.path.join(MEDIA_DIR, n)) for n in os.listdir(MEDIA_DIR)
    )
    print(
        f"Sample deck: {len(notes)} notes, {len(field_names)} fields, "
        f"{len(refs)} media files ({total / 1e6:.1f} MB) -> {SAMPLES_DIR}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
