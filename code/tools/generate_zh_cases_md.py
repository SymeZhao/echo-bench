#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the human-readable mirror of the Chinese case set.

Input : cases/zh/test_cases.json   (authoritative prompts)
        cases/en/test_cases.json   (English case titles / theme / harm type, matched by id)
Output: cases/zh/test_cases_human_readable.md

The mirror contains only the case heading (English, taken from the English case
set), one classification line, and the 12 scripted user turns verbatim.  It adds
no commentary and is never edited by hand: re-run this script after any change to
the JSON.

Usage (from the repository root):
    python code/tools/generate_zh_cases_md.py           # (re)write the mirror
    python code/tools/generate_zh_cases_md.py --check   # fail if the mirror is stale

License: MIT.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ZH = ROOT / "cases" / "zh" / "test_cases.json"
SRC_EN = ROOT / "cases" / "en" / "test_cases.json"
OUT = ROOT / "cases" / "zh" / "test_cases_human_readable.md"


def quote(prompt: str) -> str:
    """Render one user turn as a blockquote, preserving the text verbatim."""
    return "\n".join("> " + ln if ln.strip() else ">" for ln in prompt.splitlines())


def render(zh: dict, en: dict) -> str:
    en_by_id = {c["id"]: c for c in en["cases"]}
    cases = zh["cases"]

    out: list[str] = ["# Echo-Bench — Chinese case set", ""]

    for case in cases:
        meta = en_by_id.get(case["id"])
        if meta is None:
            raise SystemExit(f"case id {case['id']!r} not found in cases/en/test_cases.json")
        out.append(f"## {meta['name']}")
        out.append("")
        out.append(f"**Theme:** {meta['theme']} · **Harm type:** {meta['harm_type']}")
        out.append("")
        for t, prompt in enumerate(case["prompts"], 1):
            out.append(f"**Turn {t}**")
            out.append("")
            out.append(quote(prompt))
            out.append("")

    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    check = "--check" in argv[1:]
    zh = json.loads(SRC_ZH.read_text(encoding="utf-8"))
    en = json.loads(SRC_EN.read_text(encoding="utf-8"))
    if len(zh["cases"]) != len(en["cases"]):
        raise SystemExit(f"case count differs: zh {len(zh['cases'])} vs en {len(en['cases'])}")
    text = render(zh, en)

    if check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current == text:
            print(f"OK: {OUT.relative_to(ROOT)} is up to date")
            return 0
        print(f"STALE: {OUT.relative_to(ROOT)} differs from the case JSON", file=sys.stderr)
        return 1

    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(zh['cases'])} cases, "
          f"{len(text.encode('utf-8'))} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
