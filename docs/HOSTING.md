# Hosting: daily paper run on GitHub Actions

The workflow `.github/workflows/paper.yml` runs on GitHub's free runners (public repo), with the laptop off.

## Trigger (cron-job.org)
GitHub's own `schedule:` never fired for the sister repo, so a free cron-job.org job starts each run:
- `POST https://api.github.com/repos/Milol0608/alpaca-trader/actions/workflows/paper.yml/dispatches`, body
  `{"ref":"main"}`, headers `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`,
  `X-GitHub-Api-Version: 2026-03-10`, `Content-Type: application/json`. Success is `200`.
- Crontab `0 8 * * 1-5` in America/Denver: weekdays 10:00 New York, 30 minutes after the open.
- Token: the same fine-grained token as kalshi-forecaster, with access to both repos and only Actions: Read and write.
  It expires 2027-02-22.

## Secrets (repository → Settings → Secrets and variables → Actions)
`ALPACA_PAPER_KEY_ID`, `ALPACA_PAPER_SECRET_KEY` (set by the owner with `gh secret set`), and `SEC_CONTACT_EMAIL`.
There are no live keys anywhere, and the workflow pins `MODE=paper`.

## Manual runs
- Actions → paper → Run workflow. Tick **dry_run** to plan orders without sending them.
- Or from a terminal: `gh workflow run paper --repo Milol0608/alpaca-trader -f dry_run=true`.

## Where to see results
Each run's summary page (Actions → paper → the run) shows the account, the orders, and the forward-tracking table.
Positions and orders are also visible in the Alpaca paper dashboard.
