-- arxiv Reader: Supabase スキーマ
-- Supabase の SQL Editor で実行してください

-- 論文テーブル
CREATE TABLE IF NOT EXISTS papers (
  arxiv_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  authors JSONB NOT NULL DEFAULT '[]',
  abstract TEXT NOT NULL DEFAULT '',
  categories JSONB NOT NULL DEFAULT '[]',
  published_date DATE NOT NULL,
  arxiv_url TEXT NOT NULL,
  pdf_url TEXT,
  fetch_date DATE NOT NULL,
  score DOUBLE PRECISION NOT NULL DEFAULT 0,
  score_reason TEXT NOT NULL DEFAULT '',
  summary TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS papers_fetch_date_idx ON papers(fetch_date DESC);
CREATE INDEX IF NOT EXISTS papers_score_idx ON papers(score DESC);
CREATE INDEX IF NOT EXISTS papers_fetch_date_score_idx ON papers(fetch_date DESC, score DESC);

-- ユーザー設定テーブル (常に1行)
CREATE TABLE IF NOT EXISTS user_settings (
  id INTEGER PRIMARY KEY DEFAULT 1,
  interest_keywords JSONB NOT NULL DEFAULT '[]',
  interest_categories JSONB NOT NULL DEFAULT '["cs.AI", "cs.LG"]',
  score_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.6,
  max_results INTEGER NOT NULL DEFAULT 100,
  ollama_url TEXT NOT NULL DEFAULT 'http://localhost:11434',
  ollama_model TEXT NOT NULL DEFAULT 'qwen3:8b',
  notification_type TEXT NOT NULL DEFAULT 'none',
  slack_webhook_url TEXT,
  email_to TEXT,
  email_smtp_host TEXT DEFAULT 'smtp.gmail.com',
  email_smtp_port INTEGER DEFAULT 587,
  email_smtp_user TEXT,
  email_smtp_password TEXT,
  schedule_hour INTEGER NOT NULL DEFAULT 8,
  schedule_minute INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- デフォルト設定を挿入
INSERT INTO user_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- パイプライン実行ログ
CREATE TABLE IF NOT EXISTS pipeline_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  stage TEXT NOT NULL,       -- 'fetch' | 'score' | 'notify'
  status TEXT NOT NULL,      -- 'running' | 'success' | 'failed'
  papers_processed INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  target_date DATE NOT NULL
);

CREATE INDEX IF NOT EXISTS pipeline_logs_run_at_idx ON pipeline_logs(run_at DESC);

-- RLS: 全テーブルを anon キーで読み書き可能にする (個人用アプリ)
ALTER TABLE papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all_papers" ON papers FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_settings" ON user_settings FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_logs" ON pipeline_logs FOR ALL USING (true) WITH CHECK (true);
