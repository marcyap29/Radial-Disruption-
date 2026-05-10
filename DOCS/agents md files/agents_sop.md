# Radial Disruption — SOPs

## SOP-PLAN (new feature or multi-file change)

1. State the definition of done in one sentence.
2. List every file that will be touched.
3. Identify any external data dependency (does the change require a new download URL?).
4. Read BUG_PREVENTION.md before writing any code.
5. Write code. Read each file before editing it.
6. Run `python -m rdf_validation --dry-run` to verify no import errors.
7. Run `python -m rdf_validation` and inspect `rdf_validation/output/report.md`.
8. Close session: update context.md, planner.md, backlog.md.

## SOP-ERROR (bug fix)

1. Reproduce the error with a minimal run command.
2. Read BUG_PREVENTION.md for known failure patterns.
3. Identify the file and function where the error originates.
4. Fix only that. Do not refactor surrounding code.
5. Re-run and verify error is gone.
6. Close session.

## SOP-REVIEW (after any code change)

- `python -m rdf_validation --dry-run` must complete with no exceptions.
- `rdf_validation/output/report.md` must contain the crosswalk table, seniority profiles, and validation table.
- Every FLAGGED row must include the expert score, the specific range it violated, and which source (BLS / BEA / both) flagged it.
- No hardcoded API keys anywhere in the codebase.
- Cache directory contains downloaded files. Output directory contains report files.
