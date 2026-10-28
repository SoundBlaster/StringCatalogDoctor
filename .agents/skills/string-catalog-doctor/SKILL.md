---
name: string-catalog-doctor
description: Configure and run String Catalog Doctor to check Apple .xcstrings localization regressions, including baseline and staged Git checks.
---

# String Catalog Doctor

Use the installed `string-catalog-doctor` command or run
`python3 <doctor-checkout>/string_catalog_doctor --root <project-root>`.
Check the tool version and the consuming project's existing instructions before
changing its integration. Python 3.9+ is required.

1. Identify the catalogs and supported locales from the project, including
   targets and extensions. Set up `.string-catalog-doctor.json` at the project
   root with `version: 1`, `locales`, `baseline`, and `catalogs` entries
   containing root-relative `path` and optional `excludeKeys`. Use existing
   configuration where present. Source-language and `shouldTranslate: false`
   entries are skipped; do not exclude other keys without a reason.
2. Run the check against the working tree. The baseline is required. For an
   existing project with no baseline, inspect and record existing debt with
   `--write-baseline`; review the resulting findings. After fixing known
   findings use `--prune-baseline`. Never regenerate a baseline merely to
   suppress new failures.
3. For pre-commit use `--staged`: configuration, catalogs and baseline are
   read from the Git index. Ensure the hook invokes the intended pinned,
   unmodified tool version; preserve any existing hooks. Stage the configuration
   and baseline alongside catalog changes as needed. Test staged failures and
   unrelated unstaged edits in a disposable repository.
4. Report the command and results. Exit status 0 means the gate passed, 1
   indicates new or unpruned resolved findings, and 2 indicates invalid input.
   This is a structural check, not a linguistic review: translation meaning,
   UI layout, plural completeness and all formatting constructs are not covered.

For the current configuration example and CLI options, see the tool's README or
run the CLI with `--help`. Do not assume that passing the gate proves all
localizations are correct.
