# Tony AI team — phase 1
Tony coordinates a Coding Agent and a Testing Agent through the OpenAI Agents SDK.
This workflow runs against GitHub issues with the label `tony-ready` and comments
with a proposed implementation and QA review. It does **not** write code, run tests,
create new tasks, merge PRs, or operate an aircraft.

## Enable
1. Review and merge this branch/PR to main. GitHub scheduled workflows normally run
   from the default branch; manual runs can use the workflow's available branch.
2. In repo **Settings > Secrets and variables > Actions**, add a repository secret
   named `OPENAI_API_KEY`. Do not share it in chat or commit it.
3. Verify GitHub Actions permissions allow the workflow to write issues.
4. Create an issue, add `tony-ready`, and run **Actions > Tony AI Engineering Queue**.
5. The bot should comment its technical review and add `tony-done`.

## Boundaries
- OpenAI API billing is separate from ChatGPT Plus. Set a spending limit.
- The queue processes at most one issue per run; the recurring trigger is every
  five minutes, subject to GitHub scheduling delays.
- This is phase 1; a real autonomous coding/test/next-task loop requires
  scoped code-editing tools, isolated test execution, task-state controls and
  human sign-off for flight-critical changes.
- The separately configured 9 PM ChatGPT engineering report is not connected
  to this runner.
