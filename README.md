# String Catalog Doctor

A dependency-free Python CLI for detecting structural regressions in Apple
`.xcstrings` files. It checks configured locales for missing, empty and
non-translated units and compares common printf placeholders in scalar strings.
It does not assess translation quality, UI layout, plural completeness or
all format and interpolation forms.

Python 3.9+ is required. Run directly from a checkout:

```sh
python3 /path/to/StringCatalogDoctor/string_catalog_doctor --root /path/to/project
```

Alternatively install the package and run `string-catalog-doctor --root .`.
Place `.string-catalog-doctor.json` in the project root:

```json
{
  "version": 1,
  "locales": ["es", "fr"],
  "baseline": "strings-baseline.json",
  "catalogs": [
    {"path": "App/Localizable.xcstrings"},
    {"path": "App/InfoPlist.xcstrings", "excludeKeys": ["CFBundleName"]}
  ]
}
```

Paths are relative to the project root. Source language and
`shouldTranslate: false` entries are skipped. Exclusions are per catalog.
The baseline records known findings by catalog, key, locale, kind and detail.
Use `--write-baseline` once for existing debt and review it; use
`--prune-baseline` after fixes. Do not overwrite the baseline to hide new
findings. A deleted key does not require baseline pruning.

`--staged` reads configuration, catalogs and baseline from the Git index; it
cannot be combined with baseline modifications. Exit codes: 0 for a passing
gate, 1 for regressions or unpruned resolved findings on existing keys, 2 for
invalid inputs. Use `--config PATH` for a different root-relative config.
The caller owns installation, pinning and ensuring a pre-commit hook executes
the intended version of the tool.

Run tests using `python3 -m unittest discover -s tests -v`.
