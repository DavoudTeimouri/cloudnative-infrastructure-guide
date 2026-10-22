# USER.md — communication and work style

Contract for any agent or engineer working in this repository.

## Communication

- Terse. No filler, no pleasantries, no hedging, no restating the request.
- Pattern: `[thing] [action] [reason]`. Fragments are fine. Then the next step.
- English, unless the request is in another language — then reply in that language.
- Keep identifiers exact and verbatim: command names, flag names, error strings, file paths, API names, image tags, env vars. Do not translate or reword them.
- No articles where a fragment reads cleaner. No emoji.
- Security warnings, irreversible actions, and multi-step ordered sequences get normal prose, not fragments. Clarity wins over style there, and the terse style resumes afterwards.
- Do not narrate tool calls or report the process. Report the result: what changed, what was verified, what is left.
- Say "unverified" when a fact was not confirmed. Never present an assumption as a finding.

## Work style

- Shortest working diff wins. Boring over clever.
- Stdlib and native platform features first. Use an already-installed dependency before adding one. Never add a dependency for something a few lines can do.
- Deletion over addition. Fewest files possible.
- No unrequested abstractions: no interface with one implementation, no factory for one product, no config for a value that never changes.
- Idempotent automation. Re-runnable playbooks and scripts. Guard every task that would otherwise report a false change.
- Non-trivial logic leaves one runnable check behind: an assert-based self-check or one small test file. No frameworks. Trivial one-liners need no test.
- Never simplify away input validation at a trust boundary, error handling that prevents data loss, security, accessibility, or anything explicitly requested.
- Mark deliberate simplifications with a `ponytail:` comment naming the ceiling and the upgrade path.

## Configuration and input

- For config fields with a known value set, offer a selector list: numbered options, the default marked, Enter takes the default, a number selects, free text enters a custom value.
- Validate input at the boundary and report the reason for the rejection.

## Process

- Expect working artifacts backed by real tool output. Never claim a file, command, deployment, or test was created or executed unless it was.
- Ask before high-impact or irreversible production changes. Do not execute destructive operations, production upgrades, storage reconfiguration, or security-sensitive changes without explicit authorization.
- Incomplete tasks are rerun on resume, not abandoned.
- Preview before committing visible UX changes (menus, banners, prompts) — the user reviews the rendered output first.
- Verify syntax and logic where practical before claiming done: run the linter, the test, the parser.

## Repository-specific

- The fact store is not this repository. See `MEMORY.md`.
- Every version, tag, URL, port, or compatibility claim carries a source and a check date, or it is marked UNVERIFIED with the procedure to confirm it.
- Documentation is code. Update the affected guide, matrix, and ADR in the same change as the thing they describe.
