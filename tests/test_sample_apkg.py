#!/usr/bin/env python3
"""Sample-deck fixture contract + headless apkg builder checks (ADR 007 / T18).

The release apkg is built from repo files only (ADR 007). Part 1 validates
the committed fixtures; part 2 runs the real builder CLI into a temp dir and
independently validates the artifact — zip layout, media byte-equality,
schema-11 collection, model byte-equality with the repo templates, note/card
row shapes, guid/checksum formulas, and build determinism.

Run directly:  python3 tests/test_sample_apkg.py
Wired into ./verify. Stdlib only.
"""

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SAMPLES = os.path.join(ROOT, "samples")
MEDIA = os.path.join(SAMPLES, "media")
FRONT_PATH = os.path.join(ROOT, "Card 1 - Front.template.anki")
BACK_PATH = os.path.join(ROOT, "Card 1 - Back.template.anki")
CSS_PATH = os.path.join(ROOT, "Card 1 - Style.css")
BUILDER = os.path.join(ROOT, "build_sample_apkg.py")

MODEL_NAME = "Japanese Note type (Sentence card by Default)"
DECK_NAME = "My Life Decks::Japanese::anki-japanese-template"
DECK_TREE = ["My Life Decks", "My Life Decks::Japanese", DECK_NAME]

# Ground truth: the requirement Anki 25.x itself computed for this note type
# (from a real export, 2026-11-12). If the front template's plain field
# references change, re-derive from a real Anki export and update this.
EXPECTED_REQ = [[0, "any", [0, 4, 6, 11, 15, 16, 17]]]

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
    for match in re.findall(
        r'<img[^>]*\ssrc=["\']([^"\']+)["\']', value, re.IGNORECASE
    ):
        refs.add(match.strip())
    return {
        r
        for r in refs
        if r and not r.startswith(("data:", "http://", "https://")) and "/" not in r
    }


def field_checksum(text):
    """Contract: first 4 sha1 bytes big-endian, 0 when empty (build_sample_apkg)."""
    if not text:
        return 0
    return int.from_bytes(hashlib.sha1(text.encode("utf-8")).digest()[:4], "big")


def note_guid(field_values, tags):
    """Contract: sha1(all fields \\x1f-joined + \\x1f + sorted tags), 16 hex chars."""
    payload = "\x1f".join(field_values) + "\x1f" + "\x1f".join(sorted(tags))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def version_mtime(css_text):
    """Contract: note mtime = base + major*1e7 + minor*1e4 + patch (monotonic)."""
    major, minor, patch = re.search(
        r"Version:\s*v(\d+)\.(\d+)\.(\d+)", css_text
    ).groups()
    return 1500000000 + int(major) * 10_000_000 + int(minor) * 10_000 + int(patch)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def build_apkg(directory, name="built.apkg"):
    """Run the real builder CLI into directory; returns the path or None."""
    out = os.path.join(directory, name)
    result = subprocess.run(
        [sys.executable, BUILDER, "--out", out],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not os.path.isfile(out):
        check(
            "builder CLI exits 0",
            False,
            (result.stderr or result.stdout).strip()[-300:],
        )
        return None
    return out


def fixture_checks(fields_path, notes_path, media_dir):
    check("samples/fields.json exists", os.path.isfile(fields_path))
    check("samples/notes.json exists", os.path.isfile(notes_path))
    check("samples/media/ exists", os.path.isdir(media_dir))
    if FAIL:
        return None, None, None

    model_data = load_json(fields_path)
    notes = load_json(notes_path)

    check(
        "fields.json records the product model name",
        isinstance(model_data, dict) and model_data.get("model") == MODEL_NAME,
    )
    field_entries = model_data.get("fields") if isinstance(model_data, dict) else None
    check(
        "field entries carry name/font/size/description",
        isinstance(field_entries, list)
        and len(field_entries) >= 1
        and all(
            isinstance(f.get("name"), str)
            and f["name"]
            and isinstance(f.get("font"), str)
            and f["font"]
            and isinstance(f.get("size"), int)
            and f["size"] > 0
            and isinstance(f.get("description"), str)
            for f in field_entries
        ),
    )
    check(
        "field list has no duplicates",
        isinstance(field_entries, list)
        and len(field_entries) == len({f["name"] for f in field_entries}),
    )
    fields = [f["name"] for f in field_entries] if field_entries else []

    check("notes.json is a non-empty list", isinstance(notes, list) and len(notes) >= 1)
    if not (isinstance(notes, list) and notes):
        return fields, notes, None

    check("every note has a tags list", all(isinstance(n["tags"], list) for n in notes))
    check(
        "every note has exactly the field-list fields",
        all(set(n["fields"]) == set(fields) for n in notes),
    )
    check(
        "every field value is a string",
        all(isinstance(v, str) for n in notes for v in n["fields"].values()),
    )
    check(
        "notes sorted by Expression (deterministic fixtures)",
        [n["fields"]["Expression"] for n in notes]
        == sorted(n["fields"]["Expression"] for n in notes),
    )

    referenced = set()
    for n in notes:
        for value in n["fields"].values():
            referenced |= media_refs_in(value)
    media_meta = os.path.join(SAMPLES, "media.json")
    if not os.path.isfile(media_meta):
        check("samples/media.json exists", False)
        return fields, notes, None
    media_index = load_json(media_meta)
    kept, dangling = set(media_index["files"]), set(media_index["missing"])
    check(
        "media.json accounts for every referenced file (present or dangling)",
        referenced == kept | dangling,
        ", ".join(sorted(referenced ^ (kept | dangling))) or "ok",
    )
    on_disk = set(os.listdir(media_dir))
    check(
        "samples/media/ contains exactly the kept media files",
        on_disk == kept,
        ", ".join(sorted(on_disk ^ kept)) or "ok",
    )
    return fields, notes, kept


def builder_checks(built, fields, notes, kept):
    if built is None:
        return
    second = build_apkg(os.path.dirname(built), name="second.apkg")
    if second is None:
        return
    with open(built, "rb") as a, open(second, "rb") as b:
        check(
            "two builds are byte-identical (reproducible artifact)",
            a.read() == b.read(),
        )

    zf = zipfile.ZipFile(built)
    members = set(zf.namelist())
    numeric = {str(i) for i in range(len(kept))}
    check(
        "zip members are collection.anki2, media index, and media keys",
        members == {"collection.anki2", "media"} | numeric,
        ", ".join(sorted(members - numeric - {"collection.anki2", "media"})) or "ok",
    )
    check(
        "no meta member (importer infers legacy schema-11 package)",
        "meta" not in members,
    )

    media_index = json.loads(zf.read("media"))
    expected_index = {str(i): name for i, name in enumerate(sorted(kept))}
    check(
        "media index maps numeric keys to the media.json files",
        media_index == expected_index,
    )
    check(
        "every media entry is byte-equal to samples/media",
        all(
            zf.read(str(i)) == read_bytes(os.path.join(MEDIA, name))
            for i, name in enumerate(sorted(kept))
        ),
    )

    with tempfile.NamedTemporaryFile(suffix=".anki2", delete=False) as tmp:
        tmp.write(zf.read("collection.anki2"))
        col_path = tmp.name
    zf.close()
    con = sqlite3.connect(col_path)
    try:
        check(
            "collection integrity_check ok",
            con.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
        )
        check(
            "col schema version is 11 (legacy)",
            con.execute("select ver from col where id=1").fetchone()[0] == 11,
        )
        check(
            "note count matches notes.json",
            con.execute("select count(*) from notes").fetchone()[0] == len(notes),
        )
        check(
            "card count matches notes.json (one card per note)",
            con.execute("select count(*) from cards").fetchone()[0] == len(notes),
        )

        models = json.loads(
            con.execute("select models from col where id=1").fetchone()[0]
        )
        check(
            "exactly one model with the product name",
            len(models) == 1 and next(iter(models.values()))["name"] == MODEL_NAME,
        )
        model = next(iter(models.values()))
        front = load_text(FRONT_PATH)
        back = load_text(BACK_PATH)
        css = load_text(CSS_PATH)
        check(
            "model qfmt is byte-equal to the front template file",
            model["tmpls"][0]["qfmt"] == front,
        )
        check(
            "model afmt is byte-equal to the back template file",
            model["tmpls"][0]["afmt"] == back,
        )
        check("model css is byte-equal to the style file", model["css"] == css)
        check(
            "model has exactly one template named Card 1",
            len(model["tmpls"]) == 1 and model["tmpls"][0]["name"] == "Card 1",
        )
        check(
            "model type is standard (0) and sortf is Expression (0)",
            model["type"] == 0 and model["sortf"] == 0,
        )
        check(
            "model req matches what real Anki computes for these templates",
            model["req"] == EXPECTED_REQ,
            json.dumps(model["req"]),
        )
        entries = model["flds"]
        check(
            "model fields match fields.json names, order, font, size, description",
            [(f["name"], f["font"], f["size"], f["description"]) for f in entries]
            == [
                (f["name"], f["font"], f["size"], f["description"])
                for f in load_json(os.path.join(SAMPLES, "fields.json"))["fields"]
            ],
        )

        leaf_did = None
        decks = json.loads(
            con.execute("select decks from col where id=1").fetchone()[0]
        )
        names = [d["name"] for d in decks.values()]
        check(
            "deck tree matches the release deck hierarchy",
            names == ["Default", *DECK_TREE],
            json.dumps(names),
        )
        leaf_did = next(
            (int(k) for k, d in decks.items() if d["name"] == DECK_NAME), None
        )

        field_names = [f["name"] for f in entries]
        rows = con.execute(
            "select guid, tags, flds, sfld, csum, mid, mod, usn from notes order by id"
        ).fetchall()
        guids, problems = [], []
        expected_mod = version_mtime(css)
        for position, (row, note) in enumerate(zip(rows, notes)):
            guid, tags_str, flds, sfld, csum, mid, mod, usn = row
            values = [note["fields"][name] for name in field_names]
            if flds != "\x1f".join(values):
                problems.append(f"note {position}: flds mismatch")
            expected_tags = f" {' '.join(note['tags'])} " if note["tags"] else ""
            if tags_str != expected_tags:
                problems.append(f"note {position}: tags mismatch")
            if guid != note_guid(values, note["tags"]):
                problems.append(f"note {position}: guid mismatch")
            if csum != field_checksum(values[0]):
                problems.append(f"note {position}: csum mismatch")
            if sfld != values[0]:
                problems.append(f"note {position}: sfld mismatch")
            if mid != model["id"] or usn != -1:
                problems.append(f"note {position}: mid/usn mismatch")
            if mod != expected_mod:
                problems.append(
                    f"note {position}: mtime does not encode the CSS version"
                )
            guids.append(guid)
        check(
            "every note row matches the contract (flds/tags/guid/csum/sfld/mid/usn)",
            not problems,
            "; ".join(problems[:3]),
        )
        check("guids are unique", len(set(guids)) == len(guids))

        conf = json.loads(con.execute("select conf from col where id=1").fetchone()[0])
        check(
            "col conf is schedVer 2 with nextPos after the samples",
            conf.get("schedVer") == 2 and conf.get("nextPos") == len(notes) + 1,
        )

        note_ids = [
            r[0] for r in con.execute("select id from notes order by id").fetchall()
        ]
        card_rows = con.execute(
            "select nid, did, ord, type, queue, due, ivl, factor, data from cards order by id"
        ).fetchall()
        card_problems = []
        for position, (
            nid,
            did,
            ord_,
            type_,
            queue,
            due,
            ivl,
            factor,
            data,
        ) in enumerate(card_rows):
            if nid != note_ids[position]:  # card nid must reference its note
                card_problems.append(f"card {position}: nid mismatch")
            if did != leaf_did or ord_ != 0 or type_ != 0 or queue != 0:
                card_problems.append(f"card {position}: did/ord/type/queue mismatch")
            if due != position + 1 or ivl != 0 or factor != 0 or data != "{}":
                card_problems.append(f"card {position}: due/defaults mismatch")
        check(
            "every card row matches the contract (new card in the release deck)",
            not card_problems,
            "; ".join(card_problems[:3]),
        )
    finally:
        con.close()
        os.unlink(col_path)


def main():
    fields, notes, kept = fixture_checks(
        os.path.join(SAMPLES, "fields.json"),
        os.path.join(SAMPLES, "notes.json"),
        MEDIA,
    )
    if kept is not None and fields and notes:
        with tempfile.TemporaryDirectory() as tmpdir:
            built = build_apkg(tmpdir)
            if built:
                check("builder CLI exits 0", True)
                builder_checks(built, fields, notes, kept)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
