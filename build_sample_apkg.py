#!/usr/bin/env python3
"""Build dist/anki-japanese-template.apkg from repo files only (ADR 007 / T18).

The release artifact is a legacy Anki 2.0-format package: a zip containing
`collection.anki2` (SQLite, schema version 11 — what Anki reads for legacy
packages), the media files under numeric keys, and a `media` JSON index
mapping keys to filenames. There is no `meta` file: current Anki infers
exactly this legacy shape when `meta` is absent (rslib
`import_export/package/meta.rs`, verified 2026-11-12 — a package with only
`collection.anki2` is treated as Version::Legacy1, schema 11, hashmap media
index). Anki's own test suite round-trips legacy exports through the
modern importer (rslib `apkg/tests.rs::roundtrip`).

Everything is derived from repo files:

  qfmt/afmt/css   ← Card 1 - Front/Back.template.anki + Card 1 - Style.css
                    (repo templates are the single source of truth; tests
                    enforce byte equality against the built model)
  field metadata  ← samples/fields.json (names + font/size/description,
                    derived from the live collection by fetch_sample_deck.py)
  notes/cards     ← samples/notes.json
  media           ← samples/media.json "files" (the "missing" entries are
                    dangling references that Anki's own exporter also skips)

Determinism: ids, timestamps and the zip date are pure functions of the
inputs — two builds from the same tree are byte-identical (test-enforced).

Identifiers are sha-derived from stable names (model id ← model name, field
id ← field name, template id ← template name, deck id ← deck name), so a
later release re-imports cleanly: the modern importer matches notetypes by
id and notes by guid (rslib `apkg/import/notes.rs`). Note guids are content
hashes (all field values + tags), and note mtimes encode the version from
the CSS stamp (`Version: vM.m.p`), strictly ordered by MAJOR.MINOR.PATCH —
so under Anki's default "update if newer" import condition, unchanged notes
log as duplicates and changed releases update in place.

Known caveat: ids deliberately do NOT match the maintainer's live
collection (sha-derived vs collection-assigned). Importing a release into
a profile that already has the live note type adds a renamed duplicate
note type; releases are for fresh profiles, and the maintainer's own
collection updates via sync_to_anki.py (ADR 007).

Usage:
  python3 build_sample_apkg.py            # build dist/anki-japanese-template.apkg
  python3 build_sample_apkg.py --out PATH # build elsewhere
  python3 build_sample_apkg.py --check    # build into a temp dir + self-validate
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
FRONT_PATH = os.path.join(ROOT, "Card 1 - Front.template.anki")
BACK_PATH = os.path.join(ROOT, "Card 1 - Back.template.anki")
CSS_PATH = os.path.join(ROOT, "Card 1 - Style.css")
SAMPLES_DIR = os.path.join(ROOT, "samples")
MEDIA_DIR = os.path.join(SAMPLES_DIR, "media")
DEFAULT_OUT = os.path.join(ROOT, "dist", "anki-japanese-template.apkg")

DECK_NAME = "My Life Decks::Japanese::anki-japanese-template"
DECK_PARENTS = ["My Life Decks", "My Life Decks::Japanese"]
MODEL_NAME = "Japanese Note type (Sentence card by Default)"
TMPL_NAME = "Card 1"

# Fixed epochs and zip date: never wall-clock, so builds are reproducible.
COL_CRT = 1794452400  # collection creation, seconds (day start)
COL_MOD_MS = 1794452400000  # collection mod/scm, ms
NOTE_ID_BASE = 1794452400000  # note/card ids: base + position
VERSION_EPOCH = 1500000000  # note-mtime base; version-encoded seconds added
ZIP_DATE = (2026, 1, 1, 0, 0, 0)

LATEX_PRE = (
    "\\documentclass[12pt]{article}\n\\special{papersize=3in,5in}\n"
    "\\usepackage[utf8]{inputenc}\n\\usepackage{amssymb,amsmath}\n"
    "\\pagestyle{empty}\n\\setlength{\\parindent}{0in}\n\\begin{document}\n"
)
LATEX_POST = "\\end{document}"

# Schema 11 exactly as Anki writes it for legacy collections (mirrored from
# an Anki 25.x-written collection.anki2, including the deliberate
# integer-typed sfld column). sqlite_stat* are ANALYZE artifacts, not schema.
SCHEMA11 = """
CREATE TABLE col (
  id integer PRIMARY KEY,
  crt integer NOT NULL,
  mod integer NOT NULL,
  scm integer NOT NULL,
  ver integer NOT NULL,
  dty integer NOT NULL,
  usn integer NOT NULL,
  ls integer NOT NULL,
  conf text NOT NULL,
  models text NOT NULL,
  decks text NOT NULL,
  dconf text NOT NULL,
  tags text NOT NULL
);
CREATE TABLE notes (
  id integer PRIMARY KEY,
  guid text NOT NULL,
  mid integer NOT NULL,
  mod integer NOT NULL,
  usn integer NOT NULL,
  tags text NOT NULL,
  flds text NOT NULL,
  -- The use of type integer for sfld is deliberate, because it means that integer values in this
  -- field will sort numerically.
  sfld integer NOT NULL,
  csum integer NOT NULL,
  flags integer NOT NULL,
  data text NOT NULL
);
CREATE TABLE cards (
  id integer PRIMARY KEY,
  nid integer NOT NULL,
  did integer NOT NULL,
  ord integer NOT NULL,
  mod integer NOT NULL,
  usn integer NOT NULL,
  type integer NOT NULL,
  queue integer NOT NULL,
  due integer NOT NULL,
  ivl integer NOT NULL,
  factor integer NOT NULL,
  reps integer NOT NULL,
  lapses integer NOT NULL,
  left integer NOT NULL,
  odue integer NOT NULL,
  odid integer NOT NULL,
  flags integer NOT NULL,
  data text NOT NULL
);
CREATE TABLE revlog (
  id integer PRIMARY KEY,
  cid integer NOT NULL,
  usn integer NOT NULL,
  ease integer NOT NULL,
  ivl integer NOT NULL,
  lastIvl integer NOT NULL,
  factor integer NOT NULL,
  time integer NOT NULL,
  type integer NOT NULL
);
CREATE TABLE graves (
  usn integer NOT NULL,
  oid integer NOT NULL,
  type integer NOT NULL
);
CREATE INDEX ix_notes_usn ON notes (usn);
CREATE INDEX ix_cards_usn ON cards (usn);
CREATE INDEX ix_revlog_usn ON revlog (usn);
CREATE INDEX ix_cards_nid ON cards (nid);
CREATE INDEX ix_cards_sched ON cards (did, queue, due);
CREATE INDEX ix_revlog_cid ON revlog (cid);
CREATE INDEX ix_notes_csum ON notes (csum);
"""

# Default deck options exactly as modern Anki writes them into legacy
# collections (mirrored from the Anki 25.x stub).
DCONF_DEFAULT = {
    "1": {
        "answerAction": 0,
        "autoplay": True,
        "buryInterdayLearning": False,
        "desiredRetention": 0.9,
        "dyn": False,
        "easyDaysPercentages": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "fsrsParams5": [],
        "fsrsParams6": [],
        "fsrsWeights": [],
        "id": 1,
        "ignoreRevlogsBeforeDate": "",
        "interdayLearningMix": 0,
        "lapse": {
            "delays": [10.0],
            "leechAction": 1,
            "leechFails": 8,
            "minInt": 1,
            "mult": 0.0,
        },
        "maxTaken": 60,
        "mod": 0,
        "name": "Default",
        "new": {
            "bury": False,
            "delays": [1.0, 10.0],
            "initialFactor": 2500,
            "ints": [1, 4, 0],
            "order": 1,
            "perDay": 20,
        },
        "newGatherPriority": 0,
        "newMix": 0,
        "newPerDayMinimum": 0,
        "newSortOrder": 0,
        "questionAction": 0,
        "replayq": True,
        "rev": {
            "bury": False,
            "ease4": 1.3,
            "hardFactor": 1.2,
            "ivlFct": 1.0,
            "maxIvl": 36500,
            "perDay": 200,
        },
        "reviewOrder": 0,
        "secondsToShowAnswer": 0.0,
        "secondsToShowQuestion": 0.0,
        "sm2Retention": 0.9,
        "stopTimerOnAnswer": False,
        "timer": 0,
        "usn": 0,
        "waitForAudio": True,
        "weightSearch": "",
    }
}


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha1_hex(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def id_from_name(name):
    """Stable positive int63 derived from a stable name."""
    return (
        int.from_bytes(hashlib.sha1(name.encode("utf-8")).digest()[:8], "big")
        & 0x3FFFFFFFFFFFFFFF
    )


def field_checksum(text):
    """Anki's field checksum: first 4 sha1 bytes big-endian, 0 when empty."""
    if not text:
        return 0
    return int.from_bytes(hashlib.sha1(text.encode("utf-8")).digest()[:4], "big")


def parse_version(css_text):
    """(major, minor, patch) from the CSS stamp `Version: vM.m.p`."""
    match = re.search(r"Version:\s*v(\d+)\.(\d+)\.(\d+)", css_text)
    if not match:
        raise SystemExit(
            "ERROR: CSS version stamp missing — finish.sh stamps it before release"
        )
    return tuple(int(group) for group in match.groups())


def version_mtime(version):
    """Note mtime in seconds, strictly ordered by MAJOR.MINOR.PATCH.

    The importer updates an existing note only when the incoming mtime is
    newer; encoding the release version keeps that monotonic across
    releases while staying deterministic.
    """
    major, minor, patch = version
    return VERSION_EPOCH + major * 10_000_000 + minor * 10_000 + patch


def note_guid(field_values, tags):
    """Content-hash guid: unchanged content keeps its guid across releases."""
    payload = "\x1f".join(field_values) + "\x1f" + "\x1f".join(sorted(tags))
    return sha1_hex(payload)[:16]


def plain_ref_ords(qfmt, field_names):
    """Field ords plain-referenced in the front template (the model's req).

    Reproduces exactly what Anki computes for this note type (verified
    against a real Anki 25.x export: [[0, "any", [0, 4, 6, 11, 15, 16, 17]]]).
    Conditional markers ({{#f}}, {{/f}}, {{^f}}) are not plain references;
    modifier prefixes (e.g. `edit:`) are stripped.
    """
    names = {name: ord for ord, name in enumerate(field_names)}
    ords = set()
    for token in re.findall(r"\{\{\s*([^{}#/^]+?)\s*\}\}", qfmt):
        field = token.strip()
        if ":" in field:
            field = field.split(":", 1)[1]
        if field in names:
            ords.add(names[field])
    return sorted(ords)


def compose_model(fields_meta, qfmt, afmt, css, vmod):
    """Legacy note-type JSON mirroring modern Anki's legacy writer."""
    field_names = [f["name"] for f in fields_meta["fields"]]
    return {
        "id": id_from_name(MODEL_NAME),
        "name": MODEL_NAME,
        "type": 0,
        "mod": vmod,
        "usn": -1,
        "sortf": 0,
        "did": None,
        "tmpls": [
            {
                "name": TMPL_NAME,
                "ord": 0,
                "qfmt": qfmt,
                "afmt": afmt,
                "bqfmt": "",
                "bafmt": "",
                "did": None,
                "bfont": "",
                "bsize": 0,
                "id": id_from_name(TMPL_NAME),
            }
        ],
        "flds": [
            {
                "name": f["name"],
                "ord": ord,
                "sticky": False,
                "rtl": False,
                "font": f["font"],
                "size": f["size"],
                "description": f["description"],
                "plainText": False,
                "collapsed": False,
                "excludeFromSearch": False,
                "id": id_from_name(f["name"]),
                "tag": None,
                "preventDeletion": False,
            }
            for ord, f in enumerate(fields_meta["fields"])
        ],
        "css": css,
        "latexPre": LATEX_PRE,
        "latexPost": LATEX_POST,
        "latexsvg": False,
        "req": [[0, "any", plain_ref_ords(qfmt, field_names)]],
        "originalStockKind": 1,
    }


def compose_deck(name, deck_id, vmod):
    """Legacy deck JSON mirroring modern Anki's legacy writer."""
    return {
        "id": deck_id,
        "mod": vmod,
        "name": name,
        "usn": -1,
        "lrnToday": [0, 0],
        "revToday": [0, 0],
        "newToday": [0, 0],
        "timeToday": [0, 0],
        "collapsed": False,
        "browserCollapsed": False,
        "desc": "",
        "dyn": 0,
        "conf": 1,
        "extendNew": 0,
        "extendRev": 0,
        "reviewLimit": None,
        "newLimit": None,
        "reviewLimitToday": None,
        "newLimitToday": None,
        "desiredRetention": None,
    }


def compose_conf(model_id, note_count):
    return {
        "nextPos": note_count + 1,
        "dayLearnFirst": False,
        "sortType": "noteFld",
        "collapseTime": 1200,
        "creationOffset": 0,
        "estTimes": True,
        "dueCounts": True,
        "newSpread": 0,
        "curModel": model_id,
        "sortBackwards": False,
        "timeLim": 0,
        "curDeck": 1,
        "activeDecks": [1],
        "schedVer": 2,
        "addToCur": True,
        "sched2021": True,
    }


def build_collection_bytes(
    model, decks, conf, field_names, notes, guids, vmod, leaf_did
):
    """Create the schema-11 collection.anki2 in memory and return its bytes."""
    fd, tmp_path = tempfile.mkstemp(suffix=".anki2")
    os.close(fd)
    try:
        con = sqlite3.connect(tmp_path)
        try:
            con.executescript(SCHEMA11)
            con.execute(
                "INSERT INTO col VALUES (1, ?, ?, ?, 11, 0, 0, 0, ?, ?, ?, ?, '{}')",
                (
                    COL_CRT,
                    COL_MOD_MS,
                    COL_MOD_MS,
                    json.dumps(conf, ensure_ascii=False),
                    json.dumps({str(model["id"]): model}, ensure_ascii=False),
                    json.dumps(decks, ensure_ascii=False),
                    json.dumps(DCONF_DEFAULT, ensure_ascii=False),
                ),
            )
            for position, (note, guid) in enumerate(zip(notes, guids)):
                values = [note["fields"][name] for name in field_names]
                tags = note["tags"]
                tags_str = f" {' '.join(tags)} " if tags else ""
                con.execute(
                    "INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        NOTE_ID_BASE + position,
                        guid,
                        model["id"],
                        vmod,
                        -1,
                        tags_str,
                        "\x1f".join(values),
                        values[0],
                        field_checksum(values[0]),
                        0,
                        "",
                    ),
                )
                con.execute(
                    "INSERT INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        NOTE_ID_BASE + position,
                        NOTE_ID_BASE + position,
                        leaf_did,
                        0,
                        vmod,
                        -1,
                        0,
                        0,
                        position + 1,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        "{}",
                    ),
                )
            con.commit()
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise SystemExit(
                    f"ERROR: built collection failed integrity_check: {integrity}"
                )
        finally:
            con.close()
        return read_bytes(tmp_path)
    finally:
        os.unlink(tmp_path)


def write_apkg(out_path, col_bytes, media_files):
    """Zip collection + media + media index; fixed dates keep it deterministic."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    def entry(name):
        info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
        info.compress_type = zipfile.ZIP_DEFLATED
        return info

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(entry("collection.anki2"), col_bytes)
        for index, name in enumerate(media_files):
            with open(os.path.join(MEDIA_DIR, name), "rb") as f:
                zf.writestr(entry(str(index)), f.read())
        zf.writestr(
            entry("media"),
            json.dumps(
                {str(i): n for i, n in enumerate(media_files)}, ensure_ascii=False
            ),
        )


def load_inputs():
    qfmt = read_text(FRONT_PATH)
    afmt = read_text(BACK_PATH)
    css = read_text(CSS_PATH)
    version = parse_version(css)
    vmod = version_mtime(version)
    fields_meta = read_json(os.path.join(SAMPLES_DIR, "fields.json"))
    if fields_meta.get("model") != MODEL_NAME:
        raise SystemExit(
            f"ERROR: fields.json model {fields_meta.get('model')!r} != {MODEL_NAME!r}"
        )
    field_names = [f["name"] for f in fields_meta["fields"]]
    notes = read_json(os.path.join(SAMPLES_DIR, "notes.json"))
    media_files = read_json(os.path.join(SAMPLES_DIR, "media.json"))["files"]
    for name in media_files:
        path = os.path.join(MEDIA_DIR, name)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            raise SystemExit(
                f"ERROR: media file listed in media.json is absent/empty: {name}"
            )
    guids = [note_guid([n["fields"][f] for f in field_names], n["tags"]) for n in notes]
    if len(set(guids)) != len(guids):
        raise SystemExit("ERROR: duplicate note content — content-hash guids collide")
    return (
        qfmt,
        afmt,
        css,
        version,
        vmod,
        fields_meta,
        field_names,
        notes,
        guids,
        media_files,
    )


def build(out_path):
    """Build the apkg at out_path; returns (version, media count) for reporting."""
    (
        qfmt,
        afmt,
        css,
        version,
        vmod,
        fields_meta,
        field_names,
        notes,
        guids,
        media_files,
    ) = load_inputs()
    model = compose_model(fields_meta, qfmt, afmt, css, vmod)
    leaf_did = id_from_name(DECK_NAME)
    decks = {"1": compose_deck("Default", 1, 0)}
    for name in [*DECK_PARENTS, DECK_NAME]:
        did = id_from_name(name)
        decks[str(did)] = compose_deck(name, did, vmod)
    conf = compose_conf(model["id"], len(notes))
    col_bytes = build_collection_bytes(
        model, decks, conf, field_names, notes, guids, vmod, leaf_did
    )
    write_apkg(out_path, col_bytes, media_files)
    return version, len(media_files)


def validate(path):
    """Self-check of a built apkg (used by --check). Tests re-verify independently."""
    (
        qfmt,
        afmt,
        css,
        _version,
        _vmod,
        _fields_meta,
        field_names,
        notes,
        guids,
        media_files,
    ) = load_inputs()
    expected_members = {"collection.anki2", "media"} | {
        str(i) for i in range(len(media_files))
    }
    fd, col_extract = tempfile.mkstemp(suffix=".anki2")
    os.close(fd)
    with zipfile.ZipFile(path) as zf:
        members = set(zf.namelist())
        if members != expected_members:
            raise SystemExit(
                f"ERROR: unexpected zip members: {sorted(members ^ expected_members)}"
            )
        media_index = json.loads(zf.read("media"))
        if media_index != {str(i): n for i, n in enumerate(media_files)}:
            raise SystemExit("ERROR: media index does not match media.json")
        for index, name in enumerate(media_files):
            if zf.read(str(index)) != read_bytes(os.path.join(MEDIA_DIR, name)):
                raise SystemExit(
                    f"ERROR: media entry {name} differs from samples/media"
                )
        with open(col_extract, "wb") as f:
            f.write(zf.read("collection.anki2"))
    try:
        con = sqlite3.connect(col_extract)
        try:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise SystemExit("ERROR: collection.anki2 failed integrity_check")
            if con.execute("select ver from col where id=1").fetchone()[0] != 11:
                raise SystemExit("ERROR: collection schema version is not 11")
            if con.execute("select count(*) from notes").fetchone()[0] != len(notes):
                raise SystemExit("ERROR: note count mismatch")
            if con.execute("select count(*) from cards").fetchone()[0] != len(notes):
                raise SystemExit("ERROR: card count mismatch")
            row = con.execute("select models, decks from col where id=1").fetchone()
            models = json.loads(row[0])
            if len(models) != 1 or next(iter(models.values()))["name"] != MODEL_NAME:
                raise SystemExit("ERROR: model mismatch")
            model = next(iter(models.values()))
            if (
                model["tmpls"][0]["qfmt"] != qfmt
                or model["tmpls"][0]["afmt"] != afmt
                or model["css"] != css
            ):
                raise SystemExit("ERROR: model templates/CSS differ from repo files")
            if [f["name"] for f in model["flds"]] != field_names:
                raise SystemExit("ERROR: model field names differ from fields.json")
            stored_guids = [
                r[0] for r in con.execute("select guid from notes order by id")
            ]
            if stored_guids != guids:
                raise SystemExit("ERROR: stored guids differ from content-hash guids")
            deck_names = [d["name"] for d in json.loads(row[1]).values()]
            if DECK_NAME not in deck_names:
                raise SystemExit("ERROR: release deck missing from decks JSON")
        finally:
            con.close()
    finally:
        os.unlink(col_extract)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the release sample-deck apkg (ADR 007)"
    )
    parser.add_argument(
        "--out", default=DEFAULT_OUT, help="output path (default: dist/)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="build into a temp dir and self-validate instead of writing --out",
    )
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "check.apkg")
            version, media_count = build(path)
            validate(path)
            size = os.path.getsize(path)
            print(
                f"check ok: v{version[0]}.{version[1]}.{version[2]}, "
                f"{len(read_json(os.path.join(SAMPLES_DIR, 'notes.json')))} notes, "
                f"{media_count} media files, {size / 1e6:.1f} MB"
            )
        return 0
    version, media_count = build(args.out)
    notes_count = len(read_json(os.path.join(SAMPLES_DIR, "notes.json")))
    size = os.path.getsize(args.out)
    print(
        f"built {args.out}: v{version[0]}.{version[1]}.{version[2]}, "
        f"{notes_count} notes, {media_count} media files, {size / 1e6:.1f} MB"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
