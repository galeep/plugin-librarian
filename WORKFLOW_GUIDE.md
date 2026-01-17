# Project Workflow Guide (Draft)

## 1. Project Overview & Context
- This file consolidates the guidance from both `CLAUDE.md` (auto‑generated memory block) and the Task Master integration guide (`.taskmaster/CLAUDE.md`).
- Keep any permanent notes **outside** of the `<claude-mem-context>` tags; the block is managed automatically.

## 2. Essential Commands

| Category | Command | Purpose |
|----------|---------|---------|
| **Setup** | `task-master init` | Initialize Task Master (creates `.taskmaster/`). |
| | `task-master parse-prd .taskmaster/docs/prd.md` | Generate tasks from a PRD (Markdown preferred). |
| | `task-master models --setup` | Interactive model configuration (Claude, Perplexity, etc.). |
| **Daily Development** | `task-master list` | Show all tasks with status. |
| | `task-master next` | Get the next available task. |
| | `task-master show <id>` | View detailed task info. |
| | `task-master set-status --id=<id> --status=done` | Mark task as completed. |
| **Task Management** | `task-master add-task --prompt="desc" --research` | Create a new task with AI assistance. |
| | `task-master expand --id=<id> --research --force` | Break a task into subtasks. |
| | `task-master update-subtask --id=<id> --prompt="notes"` | Log implementation notes. |
| **Analysis & Planning** | `task-master analyze-complexity --research` | Evaluate task difficulty. |
| | `task-master complexity-report` | View complexity report. |
| | `task-master expand --all --research` | Expand all pending tasks. |
| **Dependency & Organization** | `task-master add-dependency --id=<id> --depends-on=<id>` | Declare task dependencies. |
| | `task-master move --from=<id> --to=<id>` | Re‑order tasks. |
| | `task-master validate-dependencies` | Check for circular/missing deps. |
| **Generation** | `task-master generate` | Regenerate markdown task files from `tasks.json`. |
| **Git** | `gh pr merge --squash --delete-branch` | Squash‑merge and clean up branch. |
| **MCP Integration** | See section 6 below. |

## 3. Recommended Development Loop
1. **Start** – `task-master next` → pick next task.
2. **Inspect** – `task-master show <id>` to read description, tests, notes.
3. **Log Planning** – `task-master update-subtask --id=<id> --prompt="detailed plan"` (optional).
4. **Set In‑Progress** – `task-master set-status --id=<id> --status=in-progress`.
5. **Implement** – Write code, run tests, commit.
6. **Log Progress** – `task-master update-subtask --id=<id> --prompt="what worked/didn't work"`.
7. **Internal Code Review** – Run `pr-review-toolkit:code-reviewer` BEFORE pushing. This catches issues before CI and bot reviewers see them.
8. **Push & PR** – Push branch, create PR, request reviews.
9. **Complete** – `task-master set-status --id=<id> --status=done`.
10. **Repeat** – Return to step 1.

## 4. Commit Message Guidelines

**Commit messages must be specific.** Vague messages waste reviewer time and make git history useless.

| Bad (vague) | Good (specific) |
|-------------|-----------------|
| `Address review feedback` | `Fix author re-review flow: use gh pr ready instead of gh pr review` |
| `Fix bug` | `Fix null pointer in user auth when session expires` |
| `Update code` | `Add Playwright E2E tests for keyboard input validation` |
| `Refactor` | `Extract date parsing into reusable DateUtils module` |
| `Changes` | `Increase API timeout from 5s to 30s for large file uploads` |

**Format**: `<type>: <what changed> - <why/how>` (Conventional Commits)

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`

## 5. PR Hygiene (Review Request Etiquette)

### Managing Scope Creep & Follow‑On PRs
When Copilot or a human reviewer raises a legitimate concern that a PR is adding **excessive scope** or **complexity**—especially late in the cycle—use the following criteria to decide whether to split the work into a follow‑on PR:

| # | Criterion | How to evaluate |
|---|-----------|-----------------|
| 1️⃣ | **Scope size** – Does the change affect **> 3 files** *and* modifies **multiple functional areas** (e.g., UI + backend + tests)? | Count touched files and modules; if > 3 distinct modules, consider splitting. |
| 2️⃣ | **Risk level** – Does the change introduce **new external dependencies**, **major architectural changes**, or **runtime‑performance impact**? | Look for added packages, new build steps, or performance‑critical code paths. |
| 3️⃣ | **Reviewability** – Can a reviewer reasonably understand the whole change in a single review session (≈ 30 min)? | Estimate review time; > 30 min → split. |
| 4️⃣ | **Test coverage** – Are new tests sufficient to cover the change, or does the PR require **extensive new test suites**? | If > 2 new test files or > 200 new test lines, consider a separate PR for tests. |
| 5️⃣ | **Release impact** – Will the change affect the current release cycle (e.g., breaking API, UI redesign)? | If it would delay a scheduled release, isolate into a follow‑on. |

**Action steps when the criteria are met**:
1. **Close** the current PR with a comment summarising the decision to split.
2. **Create a new "starter" PR** containing the minimal, reviewable changes (e.g., API contract, schema updates). Use the `WIP:` prefix if still incomplete.
3. **Reference** the original PR in the new PR description (`See #<old‑PR‑num>`). Link the two for traceability.
4. **Create a GitHub issue** that tracks the remaining work (e.g., `feat: complete XYZ feature – follow‑on`).
   - Include the new PR number and the original PR number in the issue body.
   - Add a label such as `follow‑on` or `needs‑review`.
5. **Add a follow‑up task** in Task Master (`task-master add-task`) to remind the team to finish the remaining work.
6. **Notify reviewers** (human or Copilot) on the new PR and optionally re‑request the bot review.
7. When the conversation or PR is finally **marked as resolved**, **comment** on the original PR with a link to the follow‑on issue (e.g., `Follow‑on work tracked in #<issue‑num>`). This makes the decision explicit and provides traceability for future viewers.

**When *not* to split**:
- The change is a **single logical unit** (e.g., bug fix, small refactor) even if it touches several files.
- Reviewers acknowledge the added scope but deem it acceptable for the current milestone.
- The PR is already labelled as a **large feature** with an agreed‑upon timeline.

By applying these concrete checks you keep PRs focused, reduce review fatigue, and maintain a clean history.

- **When to request a review**: after all changes are committed *and* CI passes.

### How to Request a Copilot Review (GitHub Copilot Pull‑Request Reviewer)

When you've finished a change and the CI checks have passed, you can ask Copilot to review the PR automatically. Copilot Review Bot is a GitHub app that provides AI‑driven feedback on code quality, style, and potential bugs.

1. **Create the PR** (if you haven't already)
   ```bash
   # Push your feature branch
   git push -u origin feature/your‑feature‑name

   # Open a PR with a descriptive title and body
   gh pr create --title "feat: add XYZ feature" \
                --body "### What this PR does\n* Brief description of the change\n* Motivation / user impact"
   ```
2. **Request a Copilot review via the GitHub API**
   The `gh` CLI does not have a built‑in flag for requesting reviewers that are bots, so you need to invoke the low‑level API endpoint:
   ```bash
   # Replace {owner}, {repo}, and {pr_number} with your values
   gh api \
     --method POST \
     /repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers \
     -f 'reviewers[]=copilot-pull-request-reviewer[bot]'
   ```
   **Example**:
   ```bash
   gh api \
     --method POST \
     /repos/galeep/sean-birthday/pulls/7/requested_reviewers \
     -f 'reviewers[]=copilot-pull-request-reviewer[bot]'
   ```
3. **What happens next**
   - Copilot receives the request and starts analyzing the diff.
   - It posts a review comment with suggestions (e.g., refactorings, potential bugs, style warnings).
   - The review appears in the PR timeline just like a human reviewer's comment.
4. **Best‑practice checklist for Copilot reviews**
   - **When to request**: after all commits are pushed, CI passes, and you've performed a quick manual sanity check.
   - **How to request**: use the `gh api` command above; add the request to the PR description if you prefer a single‑step workflow.
   - **Frequency**: request once per logical change. Additional commits keep the existing Copilot review attached; re‑request only if changes are substantial.
   - **When NOT to request**: for trivial fixes (typos, whitespace) or pure documentation updates—Copilot adds little value.
   - **Follow‑up**: review Copilot's comments, address them, and push new commits. Copilot will automatically update its review with the new diff.
   - **Escalation**: if Copilot flags a high‑severity issue, treat it like a human reviewer comment: discuss in the thread, add tests, or modify the implementation.

### When to Re‑Request Review vs. Just Resolve Threads

> ⚠️ **Critical insight: Copilot will find minutiae indefinitely.** It's designed to be thorough, not to know when to stop. You must manage this.

**DO re‑request Copilot review** after:
- Significant code changes (new features, architectural changes)
- Changes affecting multiple files with new logic
- Anything that materially changes the PR's behavior

**DON'T re‑request** for:
- Minor fixes (typos, wording, small doc updates)
- Small changes that directly address Copilot's suggestions (just resolve threads)
- Style/formatting changes only
- Whitespace or import ordering

**The rule**: If addressing Copilot's suggestion requires writing significant new code, DO re‑request review. If you're just fixing what it pointed out, resolve the thread and move on. Otherwise you'll be in an infinite loop of reviews.

5. **Automating the request (optional)**
   ```bash
   # scripts/request-copilot.sh
   #!/usr/bin/env bash
   set -euo pipefail

   PR_NUMBER=$(gh pr view --json number -q .number)
   OWNER=$(gh repo view --json owner -q .owner.login)
   REPO=$(gh repo view --json name -q .name)

   gh api \
     --method POST \
     /repos/${OWNER}/${REPO}/pulls/${PR_NUMBER}/requested_reviewers \
     -f 'reviewers[]=copilot-pull-request-reviewer[bot]'
   ```
   Run it after creating the PR:
   ```bash
   chmod +x scripts/request-copilot.sh
   ./scripts/request-copilot.sh
   ```
6. **Add a reminder to your PR template (optional)**
   If you use a PR template (`.github/pull_request_template.md`), include a line like:
   ```markdown
   - [ ] Request Copilot review (run `./scripts/request-copilot.sh` or use the `gh api` command)
   ```
   This makes the step visible to everyone on the team and won't be missed.

- **How to request**: tag reviewers in the PR description (`@team` or specific usernames).
- **Rationale**: reviewers should always explain why a suggestion is accepted, modified, or rejected, ensuring transparent decision‑making.
- **Response expectations**: reviewers acknowledge within 24 h, feedback within 48 h.
- **Handling WIP PRs**:
  - Prefix title with `WIP:`.
  - Keep required status checks disabled until ready.
  - Remove `WIP:` once ready and request reviews.
- **Closing conversations**:
  - After merge, comment on related issues and close them.
  - For stale discussions, add a comment noting archival.

## 6. MCP (Model‑Context‑Protocol) Integration

> ⚠️ **Important** – Always run `mcp-cli info <server>/<tool>` before any `mcp-cli call`. This is mandatory, not optional.

| Step | Command | Note |
|------|---------|------|
| Discover servers | `mcp-cli servers` | Lists available MCP servers. |
| List tools | `mcp-cli tools` | Shows all MCP tools. |
| Inspect schema | `mcp-cli info task-master-ai/get_tasks` (repeat for each) | **Mandatory** before calling. |
| Call tool | `mcp-cli call task-master-ai/get_tasks '{}'` | Execute after schema check. |
| Tool tiers | `core` (7 tools), `standard` (14), `all` (44+) – set via `TASK_MASTER_TOOLS` in `.mcp.json`. |
| Essential core tools | `get_tasks`, `next_task`, `get_task`, `set_task_status`, `update_subtask`, `parse_prd`, `expand_task`. |
| Enable in Claude | Add `mcp__task_master_ai__*` to `.claude/settings.json` `allowedTools`. |

## 7. Custom Slash Commands (Claude Code)
Create markdown files under `.claude/commands/`:
- **`taskmaster-next.md`** – "Find the next available Task Master task and show its details."
- **`taskmaster-complete.md`** – "Complete a Task Master task: $ARGUMENTS. Steps: show task, verify implementation, run tests, mark done, show next."
These can be invoked as `/taskmaster-next` and `/taskmaster-complete`.

## 8. Tool Allowlist (Claude Code Settings)
Add to `.claude/settings.json`:
```json
{
  "allowedTools": [
    "Edit",
    "Bash(task-master *)",
    "Bash(git commit:*)",
    "Bash(git add:*)",
    "Bash(npm run *)",
    "mcp__task_master_ai__*"
  ]
}
```

## 9. Quick Checklist for New Projects
1. Copy this draft to `WORKFLOW_GUIDE.md` in the new repo.
2. Fill in the **Overview** with a project‑specific description.
3. Adjust the branching strategy if needed.
4. Verify the PR hygiene section matches team conventions.
5. Commit and push; follow the mandatory PR workflow defined in `CLAUDE.md`.

---
*Generated with Claude Code*
