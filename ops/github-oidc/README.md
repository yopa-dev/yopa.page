# GitHub OIDC configuration

The operational trust and permission JSON is maintained in the private [codex-hub repository](https://github.com/yopa-dev/codex-hub/tree/fcec2813521a0b53ff9d3aa35acf648a2004d98f/ops/yopa.page/github-oidc). Access requires repository permission. AWS IAM enforces the applied policies; changing a Git file does not change AWS. No AWS permission or site deployment changes as part of this move.

The public site workflow uses `AWS_PLAN_ROLE_ARN` for read-only plans and `AWS_DEPLOY_ROLE_ARN` for main-only deployment. These repository variables identify roles; they are not access keys. Trust must restrict the exact repository identity, allowed event/branch and STS audience. Keep main review and required checks enabled. An owner PAT used by a bot has the owner's identity; human-only merge also requires operating discipline.

For a new project, start from `trust.example.json`, replace every placeholder in private configuration, and separately define narrowly scoped resource permissions. The example is not deployable as written. Do not add static AWS keys as an authentication fallback.

Read-only plans use `-lock=false` and must never be applied. Main deployment retains normal state locking and the existing plan gates. Previous Git history, public Terraform and CI output may still reveal resource metadata. Moving configuration does not remove past disclosure or guarantee that all identifiers stay private.

## Secret scan

The required `secret-scan` check scans all available Git history and the working tree, with output redacted. A SHA-pinned Gitleaks v3 Action is used when `GITLEAKS_LICENSE` is available. Without a license (including fork PRs), the checksum-pinned open-source CLI keeps the required scan running. A failed Action is not bypassed by a fallback. The Action-installed CLI also runs the full scans because the Action's default PR scan covers only a commit range. Comments and result artifacts are disabled.

Organization licenses are available from https://gitleaks.io/; store the key as the repository secret `GITLEAKS_LICENSE`, never in source or chat. Keep the scanner version fixed and review updates. The narrow public Firebase identifier exception remains unchanged.
