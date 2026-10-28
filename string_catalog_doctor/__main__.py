#!/usr/bin/env python3
"""Check String Catalog regressions against a reviewable legacy baseline."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
FORMAT = re.compile(r"%(?:(\d+)\$)?(?:\([^)]+\))?[-+#0 ']*(?:\d+)?(?:\.\d+)?(hh|ll|h|l|z|t|j|L)?([@diouxXfFeEgGaAcCsSp])")


def read_file(path, staged):
    if staged:
        result = subprocess.run(["git", "show", ":" + path], cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            raise ValueError(f"cannot read staged {path}: {result.stderr.strip()}")
        return result.stdout
    return (ROOT / path).read_text(encoding="utf-8")


def placeholders(value):
    """Compare printf argument positions and types, including positional reorder."""
    args = []
    index = 0
    implicit = 0
    while index < len(value):
        if value[index] != "%":
            index += 1
            continue
        if value[index:index + 2] == "%%":
            index += 2
            continue
        match = FORMAT.match(value, index)
        if match is None:
            index += 1
            continue
        implicit += 1
        position = int(match.group(1)) if match.group(1) else implicit
        args.append((position, (match.group(2) or "") + match.group(3)))
        index = match.end()
    return sorted(args)


def units(node, path=""):
    if not isinstance(node, dict):
        return
    if "stringUnit" in node:
        yield path, node["stringUnit"]
    for group in ("variations", "substitutions"):
        for key, child in node.get(group, {}).items():
            if group == "variations":
                for variant, value in child.items():
                    yield from units(value, f"{path}/{key}/{variant}")
            else:
                yield from units(child, f"{path}/substitution/{key}")


def check_catalog(path, doc, locales, excluded_keys=()):
    if not isinstance(doc.get("strings"), dict):
        raise ValueError(f"{path}: missing strings object")
    issues = []
    source_language = doc.get("sourceLanguage", "en")
    for key, entry in sorted(doc["strings"].items()):
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: malformed entry {key!r}")
        if entry.get("shouldTranslate") is False or key in excluded_keys:
            continue
        for locale in locales:
            if locale == source_language:
                continue
            translation = entry.get("localizations", {}).get(locale)
            def issue(kind, detail=""):
                issues.append({"catalog": path, "key": key, "locale": locale, "kind": kind, "detail": detail})
            if translation is None:
                issue("missing")
                continue
            found = list(units(translation))
            if not found:
                issue("missing-unit")
                continue
            for variant, unit in found:
                if not isinstance(unit, dict):
                    issue("invalid-unit", variant)
                    continue
                value = unit.get("value")
                if not isinstance(value, str) or not value.strip():
                    issue("empty", variant)
                elif unit.get("state") != "translated":
                    issue("untranslated", variant)
                elif not variant and placeholders(key) != placeholders(value):
                    issue("placeholder", variant)
    return issues


def fingerprint(issue):
    return tuple(issue[k] for k in ("catalog", "key", "locale", "kind", "detail"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="consumer repository root (default: current directory)")
    parser.add_argument("--config", default=".string-catalog-doctor.json", help="configuration path relative to root")
    parser.add_argument("--staged", action="store_true", help="read catalogs and baseline from the Git index")
    parser.add_argument("--write-baseline", action="store_true", help="replace the baseline with current findings")
    parser.add_argument("--prune-baseline", action="store_true", help="remove resolved baseline findings without adding new ones")
    args = parser.parse_args()
    if args.staged and (args.write_baseline or args.prune_baseline):
        parser.error("--staged cannot be combined with baseline changes")
    if args.write_baseline and args.prune_baseline:
        parser.error("choose one baseline operation")
    global ROOT
    ROOT = Path(args.root).resolve()
    try:
        config = json.loads(read_file(args.config, args.staged))
        if not isinstance(config, dict) or config.get("version") != 1:
            raise ValueError("unsupported configuration version")
        catalogs = config.get("catalogs")
        locales = config.get("locales")
        baseline_path = config.get("baseline")
        if (not isinstance(catalogs, list) or not catalogs or
                not isinstance(locales, list) or not locales or
                not all(isinstance(x, str) and x for x in locales) or
                not isinstance(baseline_path, str) or not baseline_path):
            raise ValueError("configuration requires non-empty catalogs, locales and baseline")
        paths = [baseline_path, args.config]
        for catalog in catalogs:
            if (not isinstance(catalog, dict) or not isinstance(catalog.get("path"), str) or
                    not catalog["path"] or not isinstance(catalog.get("excludeKeys", []), list) or
                    not all(isinstance(x, str) for x in catalog.get("excludeKeys", []))):
                raise ValueError("invalid catalog configuration")
            paths.append(catalog["path"])
        if any(Path(p).is_absolute() or ".." in Path(p).parts for p in paths):
            raise ValueError("configuration paths must be relative to root without ..")
        if len({c["path"] for c in catalogs}) != len(catalogs):
            raise ValueError("duplicate catalog paths")
        issues = []
        keys = {}
        for catalog in catalogs:
            path = catalog["path"]
            document = json.loads(read_file(path, args.staged))
            issues.extend(check_catalog(path, document, locales, catalog.get("excludeKeys", [])))
            keys[path] = set(document["strings"])
        if args.write_baseline:
            (ROOT / baseline_path).write_text(json.dumps({"version": 1, "issues": issues}, ensure_ascii=False, indent=2) + "\n")
            print(f"Recorded {len(issues)} findings in {baseline_path}.")
            return 0
        baseline = json.loads(read_file(baseline_path, args.staged))
        if baseline.get("version") != 1 or not isinstance(baseline.get("issues"), list):
            raise ValueError("invalid baseline format")
        known = {fingerprint(item) for item in baseline["issues"]}
        current = {fingerprint(item) for item in issues}
        if args.prune_baseline:
            baseline["issues"] = [item for item in baseline["issues"] if fingerprint(item) in current]
            (ROOT / baseline_path).write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n")
            print(f"Removed {len(known - current)} resolved baseline entries; no new findings were added.")
            return 0
        new = [item for item in issues if fingerprint(item) not in known]
        for item in new:
            print(f"{item['catalog']}: {item['locale']}: {item['key']!r}: {item['kind']} {item['detail']}")
        print(f"strings-check: {len(new)} new issues, {len(current & known)} baseline issues, "
              f"{len(known - current)} resolved baseline entries.")
        resolved = {item for item in known - current if item[1] in keys.get(item[0], set())}
        if resolved:
            print("Remove resolved findings with: string-catalog-doctor --prune-baseline")
        return 1 if new or resolved else 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError) as error:
        print(f"strings-check: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
