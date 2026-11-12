# Project conventions for agents

Read `agent.md` (architecture) and `CONTRIBUTING.md` (workflow) before changing code.

## Git conventions (also in CONTRIBUTING.md section 6)

### Branch names

Format: `<type>/<short-kebab-description>`, lowercase, ASCII, at most about 50 characters, no spaces or underscores.

| Type | Use for | Example |
|---|---|---|
| `feat` | new behaviour or endpoint | `feat/user-profile-endpoint` |
| `fix` | bug fix | `fix/login-timing-leak` |
| `refactor` | no behaviour change | `refactor/split-auth-service` |
| `test` | tests only | `test/route-coverage-edge-cases` |
| `docs` | documentation only | `docs/contributing-guide` |
| `chore` | tooling, deps, CI, config | `chore/bump-ruff` |
| `hotfix` | urgent production fix, branched from `main` | `hotfix/jwt-expiry` |

- Branch from an up-to-date `main`. Never commit directly to `main`.
- One branch per feature or fix; keep it short-lived and delete it after merge.
- Ticket or Spec Kit feature number goes right after the type: `feat/123-user-profile`, `feat/003-password-reset`.
- Agents: create the branch before making changes, and never reuse a branch for unrelated work.

### Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `<type>(<optional scope>): <summary>`.

- Types match the branch types, plus `perf` and `build`. Scope is the layer or feature, for example `auth`, `repo`, `transport`, `storage`, `deps`.
- Summary: imperative mood ("add", not "added"), lowercase, no trailing period, 72 characters or fewer.
- Body (optional): explain why, not what, wrapped at about 72 characters. Breaking changes: `!` after the type and a `BREAKING CHANGE:` footer.
- One logical change per commit. Never commit `.env`, secrets or generated indexes.

Examples: `feat(auth): add signup and login endpoints`, `fix(repo): map unique violation to EmailAlreadyExists`.

<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tool** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Name a file or symbol in the query to read its current line-numbered source. If it's listed but deferred, load it by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` prints the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
<!-- CODEGRAPH_END -->
