"""
Parser utilities for accession numbers, range expressions, and part designations.
"""

import re
from typing import List, Tuple


def expand_part_designation(part_str: str) -> List[str]:
    """
    Expands part designations into a list of individual part strings.
    Supports:
    - Lists of parts: 'A1,A3,A4' -> ['A1', 'A3', 'A4']
    - Comma-separated with inferred prefix: 'A1,3,4' -> ['A1', 'A3', 'A4']
    - Multiple prefixes with ranges: 'A1-3,B1-3' -> ['A1', 'A2', 'A3', 'B1', 'B2', 'B3']
    - Whole Item symbol '*': '*' -> ['']
    """
    if not part_str:
        return [""]

    chunks = [c.strip() for c in part_str.split(",") if c.strip()]
    results = []
    current_prefix = ""

    for chunk in chunks:
        if chunk == "*":
            results.append("")
            continue
        m = re.match(r"^([A-Za-z]+)(.*)$", chunk)
        if m:
            prefix, rest = m.groups()
            prefix = prefix.upper()
            current_prefix = prefix
            rest = rest.strip()
            if not rest:
                results.append(prefix)
                continue
            rest = re.sub(r"^([-\s]*)" + re.escape(prefix), r"\1", rest)
            rest = re.sub(r"-" + re.escape(prefix), "-", rest)
            if "-" in rest:
                parts = rest.split("-")
                if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                    s, e = int(parts[0]), int(parts[1])
                    for n in range(s, e + 1):
                        results.append(f"{prefix}{n}")
                else:
                    results.append(f"{prefix}{rest}")
            else:
                results.append(f"{prefix}{rest}")
        else:
            if "-" in chunk:
                parts = chunk.split("-")
                if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                    s, e = int(parts[0]), int(parts[1])
                    for n in range(s, e + 1):
                        results.append(f"{current_prefix}{n}")
                else:
                    results.append(f"{current_prefix}{chunk}")
            else:
                results.append(f"{current_prefix}{chunk}")

    return results


def parse_range_expression(expr: str, zfill_len: int = 0) -> List[str]:
    """
    Parses number/range expressions like '2024-2026', '44, 46', '16-24', '1, 3, 5-7'.
    Returns list of string values with optional zero padding.
    """
    if not expr:
        return []
    results = []
    chunks = [c.strip() for c in expr.split(",") if c.strip()]
    for chunk in chunks:
        if "-" in chunk:
            parts = chunk.split("-")
            if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                start, end = int(parts[0]), int(parts[1])
                for i in range(start, end + 1):
                    val_str = str(i)
                    if zfill_len > 0:
                        val_str = val_str.zfill(zfill_len)
                    results.append(val_str)
            else:
                results.append(chunk)
        else:
            val_str = chunk
            if zfill_len > 0 and chunk.isdigit():
                val_str = chunk.zfill(zfill_len)
            results.append(val_str)
    return results


def split_full_identifiers(s: str) -> List[str]:
    """Splits string by comma when followed by year.batch.item pattern."""
    parts = re.split(r",\s*(?=\d{1,4}\.\d+)", s.strip())
    return [p.strip() for p in parts if p.strip()]


def parse_identifiers(
    identifier_str: str = None,
    year: str = None,
    item: str = None,
    batch: str = None,
    part: str = None
) -> List[Tuple[str, str]]:
    """
    Parses and validates artifact identifier into a list of (year, rest_identifier) tuples.
    Supports single items, multi-part lists, and ranges (e.g. '2026.1.1A1,A3,A4' or '2026.1.1A1-3,B1-3').
    """
    if identifier_str:
        tokens = split_full_identifiers(identifier_str)
        if len(tokens) > 1:
            results = []
            for t in tokens:
                results.extend(parse_identifiers(identifier_str=t))
            return results

        s = tokens[0]
        m = re.match(r"^(\d{1,4})\.(\d+)\.(\d+)(.*)$", s)
        if m:
            yr, ba, it, prt = m.groups()
            parts = expand_part_designation(prt)
            return [(yr.zfill(4), f"{ba.zfill(2)}.{it.zfill(2)}{p}") for p in parts]
        m2 = re.match(r"^(\d{1,4})\.(.+)$", s)
        if m2:
            return [(m2.group(1).zfill(4), m2.group(2))]
        raise ValueError(
            f"Invalid identifier format '{identifier_str}'. Expected format: YEAR.BATCH#.ITEM#[PART] (e.g. 2026.1.1 or 2026.01.01A1 or 2026.01.01A1-3,B1-3)"
        )

    if year and item and batch:
        yr_padded = str(year).strip().zfill(4)
        ba_padded = str(batch).strip().zfill(2)
        it_padded = str(item).strip().zfill(2)
        parts = expand_part_designation(part) if part else [""]
        return [(yr_padded, f"{ba_padded}.{it_padded}{p}") for p in parts]

    raise ValueError("Must provide either a full identifier string (e.g., '2026.1.1A1') or --year, --batch, and --item arguments.")
