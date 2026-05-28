# Running shell commands

These rules exist to avoid needless permission prompts. Follow them exactly.

## Never prepend a redundant `cd`

The working directory is already the project root
(`/Users/kk/Developer/2026-05_FM-KB-outreach-Warsaw`). Do **not** begin a Bash
command with `cd /Users/kk/Developer/2026-05_FM-KB-outreach-Warsaw` (or any `cd`
to a path you are already in). A leading `cd` in a compound command makes Claude
Code prompt for approval — even when every other operation is read-only and would
otherwise run silently.

When you genuinely need to act in a different directory, prefer:
- `git -C <path> <subcommand>`
- `invoke -r <path> <task>`
- a subshell: `( cd <path> && <command> )`

…instead of a bare leading `cd`.

## Prefer `grep`/`ls` over inline `python3 -c` for simple file checks

For questions like "is this symbol in that file?", "is X listed in the `pre=[...]`
list?", or "does this file exist?", use `grep`, `grep -n`, `grep -rn`, or `ls`.
These are auto-allowed and run without a prompt. Reserve `python3 -c "..."` for
work that genuinely needs Python — inline interpreter calls are treated as
arbitrary code execution and always prompt.
