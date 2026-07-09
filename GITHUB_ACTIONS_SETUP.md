# GitHub Actions setup for HYDRA-PRIME

The GitHub App used by this Arena session does **not** currently have the GitHub `workflows` permission. A push that created `.github/workflows/hydra-prime.yml` was rejected by GitHub with:

```text
refusing to allow a GitHub App to create or update workflow `.github/workflows/hydra-prime.yml` without `workflows` permission
```

Therefore the workflow is included as a template instead of being installed directly:

```text
github-actions/hydra-prime.yml.template
```

## To activate it

After reconnecting GitHub/Arena with workflow permission, or from a local GitHub-authenticated checkout with workflow permission:

```bash
mkdir -p .github/workflows
cp github-actions/hydra-prime.yml.template .github/workflows/hydra-prime.yml
git add .github/workflows/hydra-prime.yml
git commit -m "Enable HYDRA-PRIME GitHub Actions feed runner"
git push origin arena/019f45e7-aduns-fx
```

## What the workflow runs

- Unit tests
- One live feed-health cycle
- Public/live feed acquisition attempts
- Strict real-data opportunity audit
- Optional daily audits
- Artifact upload for reports/logs

Manual run after activation:

```bash
gh workflow run hydra-prime.yml \
  --ref arena/019f45e7-aduns-fx \
  -f start_date=2026-01-01 \
  -f end_date=2026-01-31 \
  -f daily_audit=true \
  -f fail_on_blocked=false
```

The workflow does not fabricate feed data. If feeds are missing or unreachable, reports say `BLOCKED`.
