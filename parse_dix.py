#!/usr/bin/env python3
"""
Parse apertium-cos.cos.dix and generate lexique-apertium.js
Surface form = stem (from <i> or <i>+<b>+<i>) + left-side suffix (from pardef <l> elements)
"""

import xml.etree.ElementTree as ET
import re

DIX = "apertium-cos.cos.dix"
OUT_JS = "lexique-apertium.js"

def get_l_text(entry):
    """Extract left-side surface text from an <e> element (inside a pardef)."""
    p = entry.find("p")
    if p is None:
        return None
    l = p.find("l")
    if l is None:
        return None
    # Concatenate direct text + text of child elements (ignore <s> tags, collect <b> as space)
    parts = []
    if l.text:
        parts.append(l.text)
    for child in l:
        if child.tag == "b":
            parts.append(" ")
        # ignore <s> (symbol tags)
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)

def get_stem(entry):
    """Extract stem from a main-section <e> element.
    Handles <i>text</i> and multi-<i> with <b> (space) in between.
    """
    parts = []
    # Direct text of <e> (rare)
    if entry.text and entry.text.strip():
        parts.append(entry.text.strip())
    for child in entry:
        if child.tag == "i":
            text = (child.text or "") + "".join(
                (" " if gc.tag == "b" else "") + (gc.tail or "")
                for gc in child
            )
            parts.append(text)
        elif child.tag == "b":
            parts.append(" ")
        # <par> is the paradigm ref — stop collecting stem after it
        elif child.tag == "par":
            break
        if child.tail and child.tail.strip():
            parts.append(child.tail.strip())
    return "".join(parts)

def get_par_ref(entry):
    """Return the paradigm name referenced by a main-section <e> element."""
    par = entry.find("par")
    if par is not None:
        return par.get("n", "")
    return ""

# ── Parse ──────────────────────────────────────────────────────────────────────
tree = ET.parse(DIX)
root = tree.getroot()

# 1. Build paradigm map: name → list of l-side suffixes
pardefs_el = root.find("pardefs")
paradigms = {}  # name → [suffix, ...]

for pardef in pardefs_el.findall("pardef"):
    name = pardef.get("n", "")
    suffixes = []
    for e in pardef.findall("e"):
        # Skip right-only entries (r="RL") — they are not surface forms
        if e.get("r") == "RL":
            continue
        # Skip entries with <re> (regex patterns over numbers etc.)
        if e.find("re") is not None:
            continue
        l_text = get_l_text(e)
        if l_text is not None:
            suffixes.append(l_text)
    paradigms[name] = suffixes

# 2. Walk main sections and combine stem + suffix
words = set()

for section in root.findall("section"):
    for e in section.findall("e"):
        # Skip RL-only entries
        if e.get("r") == "RL":
            continue
        # Skip regex entries
        if e.find("re") is not None:
            continue

        stem = get_stem(e)
        par_ref = get_par_ref(e)

        if not par_ref:
            # Entry with no paradigm: the stem itself is the word
            if stem:
                words.add(stem.lower())
            continue

        suffixes = paradigms.get(par_ref, [])
        if not suffixes:
            # Paradigm exists but has no l-side forms (e.g. invariable words)
            if stem:
                words.add(stem.lower())
            continue

        for suffix in suffixes:
            form = (stem + suffix).strip()
            if form and not re.search(r"[0-9\[\]()\.\?!;:,\"'«»–\-]", form):
                words.add(form.lower())

# Remove empty strings
words.discard("")

print(f"Total surface forms extracted: {len(words)}")

# ── Write JS ──────────────────────────────────────────────────────────────────
sorted_words = sorted(words)

with open(OUT_JS, "w", encoding="utf-8") as f:
    f.write("// Lexique corse généré depuis apertium-cos.cos.dix\n")
    f.write(f"// {len(sorted_words)} formes de surface\n")
    f.write("const LEXIQUE = new Set([\n")
    for w in sorted_words:
        escaped = w.replace("\\", "\\\\").replace('"', '\\"')
        f.write(f'  "{escaped}",\n')
    f.write("]);\n")

print(f"Written: {OUT_JS}")
