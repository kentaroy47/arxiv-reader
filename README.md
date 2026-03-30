# arxiv-reader

A daily arxiv paper digest that fetches papers by category, scores them against your research interests using a local LLM (Ollama), summarizes the top papers, and sends a Slack (or email) notification.

## Architecture

```
arxiv RSS feeds
      ↓
  fetch papers
      ↓
  LLM scoring (Ollama)  ←── your interest keywords
      ↓
  save to Supabase
      ↓
  fetch affiliations (arxiv HTML)
      ↓
  PDF download + summarization (Ollama)
      ↓
  Slack / Email notification
```

**Stack**
- **Backend**: Python (asyncio, httpx, feedparser)
- **LLM**: Ollama running locally (tested with `qwen2.5:32b`, `qwen3:32b`)
- **Database**: Supabase (PostgreSQL)
- **Frontend**: Flutter web app (reads from Supabase)
- **Notifications**: Slack Incoming Webhooks or SMTP email

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally
- Supabase project (free tier works)
- Slack workspace with Incoming Webhooks enabled (optional)

## Setup

### 1. Supabase

Run `supabase/schema.sql` in your Supabase project's SQL Editor.

Then apply the affiliations column added during setup:
```sql
alter table papers add column if not exists affiliations text[] default '{}';
```

### 2. Ollama

Pull a model:
```bash
ollama pull qwen3:32b
# or
ollama pull qwen2.5:32b-instruct-q4_K_M
```

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # edit with your values
```

`.env` keys:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:32b
```

### 4. Configure settings in Supabase

Edit `user_settings` (id=1) directly in Supabase Table Editor, or via SQL:

```sql
update user_settings set
  interest_keywords  = '["large language model", "LLM inference", "autonomous driving", "lidar"]',
  interest_categories = '["cs.AI", "cs.LG", "cs.RO", "cs.CV"]',
  score_threshold    = 0.65,
  ollama_model       = 'qwen3:32b',
  notification_type  = 'slack',
  slack_webhook_url  = 'https://hooks.slack.com/services/...'
where id = 1;
```

### 5. Slack (optional)

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From scratch
2. Enable **Incoming Webhooks**
3. Add New Webhook to Workspace → select channel
4. Copy the webhook URL into `user_settings.slack_webhook_url`

## Usage

**Run immediately:**
```bash
cd backend
python main.py --run-now
```

**Run as daily scheduler** (runs at the hour/minute set in `user_settings`):
```bash
python main.py
```

**Backfill a specific date** (RSS only returns the current batch, so this is mainly for re-processing):
```bash
python main.py --run-now --date 2026-03-30
```

## Scoring

Papers are scored 0.0–1.0 against your `interest_keywords`:

| Score | Meaning |
|-------|---------|
| 0.9–1.0 | Directly matches core interests — must-read |
| 0.7–0.9 | Clearly related — worth reading |
| 0.5–0.7 | Peripheral — read if time allows |
| 0.0–0.5 | Largely unrelated |

Only papers at or above `score_threshold` are summarized and included in notifications.

## Supabase Tables

| Table | Description |
|-------|-------------|
| `papers` | Fetched papers with scores, summaries, affiliations |
| `user_settings` | Single-row config (id=1) |
| `pipeline_logs` | Per-stage run logs (fetch / score / summarize / notify) |

## Slack Notification Format

```
📄 arxiv Daily Digest (2026-03-30)
Papers above threshold: 5

• [92%] Some Great Paper Title
  👤 Author A, Author B et al.  (MIT / Stanford)
  _Directly addresses LLM inference optimization with 3x speedup_
  本論文では...（日本語要約）
```
