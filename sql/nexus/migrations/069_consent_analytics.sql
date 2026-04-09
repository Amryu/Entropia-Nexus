ALTER TABLE consent_log
ADD COLUMN IF NOT EXISTS analytics_consent TEXT NOT NULL DEFAULT 'denied'
CHECK (analytics_consent IN ('granted', 'denied'));
