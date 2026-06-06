# Implementation Stage

You are implementing the solution for **{{ issue.identifier }}**: {{ issue.title }}

**Current status:** {{ issue.state }}
**Labels:** {{ issue.labels }}
**URL:** {{ issue.url }}

## Issue description

{% if issue.description %}
{{ issue.description }}
{% else %}
No description provided.
{% endif %}

## Objective

Implement the solution, create a PR, and ensure it passes all quality checks.

## First run

1. Read the investigation summary from the Linear comments.
2. Read the relevant source files identified in the investigation.
3. Create a feature branch from `master`:
   ```
   git checkout -b {{ issue.identifier | lower }}-<short-description>
   ```
4. Implement the changes with clean, logical commits.
5. Run the full quality suite:
   - Type checking
   - Linting
   - All tests
6. Fix any failures before proceeding.
7. Push the branch and create a PR:
   ```
   git push -u origin HEAD
   gh pr create --title "{{ issue.identifier }}: <concise title>" --body "<description>"
   ```
8. Link the PR to the Linear issue.
9. Update the workpad with: what was done, what was tested, any known limitations.

## Rework run

If this is a rework run (a branch and PR already exist):

1. Pull changes (if any) from `master` branch.
2. Find the existing PR:
   ```
   gh pr list --head <branch-name>
   ```
3. Read review comments and requested changes:
   ```
   gh pr view <number> --comments
   ```
4. Address each piece of feedback specifically.
5. Run the full quality suite again.
6. Push new commits to the existing branch (do not force-push).
7. Post a comment on the GitHub PR summarising the rework:
   - Which review comments were addressed
   - What was modified
   - Any decisions or trade-offs
8. Append a rework section to the Linear workpad.

## Quality bar

Before finishing, verify:

- [ ] All tests pass
- [ ] No type errors
- [ ] No lint errors
- [ ] All acceptance criteria from the ticket description met
- [ ] Master branch does not have changes, that affect this implementation
- [ ] PR created (or updated) and linked to Linear issue
- [ ] Workpad updated with completion summary
