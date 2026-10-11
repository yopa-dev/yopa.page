# AGENTS.md

Agent instructions for the yopa.page repository.

## Blog operation playbooks

Task-specific guidance for agents operating on this blog lives in
`docs/agent-playbooks/`. Read the relevant playbook before acting:

- **Inbound article triage** (scan web reading, identify article candidates, report):
  `docs/agent-playbooks/inbound-article-triage.md`

Re-read the playbook that matches your current task each run. The playbooks are the
source of truth for how work on this blog should be done.

## yopa-dev release boundary

- Keep main protected: human-only push/merge, required review and static-checks/secret-scan. GitHub App has no bypass.
- Use OIDC repository variables for separate read-only planning and main-only deployment roles; no static AWS keys or GH_TOKEN fallback. Operational role JSON lives in the private codex-hub ops/yopa.page/github-oidc/ directory; ops/github-oidc/ here contains public documentation and placeholders only.
