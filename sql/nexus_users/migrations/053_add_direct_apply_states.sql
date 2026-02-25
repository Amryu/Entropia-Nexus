-- Migration: Add DirectApply and ApplyFailed states for admin pass-through changes
-- DirectApply: admin-only state that instructs the bot to apply immediately without review
-- ApplyFailed: direct apply attempt failed; admin can retry or discard via Discord DM

-- Add new enum values
ALTER TYPE public.change_state ADD VALUE IF NOT EXISTS 'DirectApply';
ALTER TYPE public.change_state ADD VALUE IF NOT EXISTS 'ApplyFailed';

-- Update the content_updated_at trigger to include DirectApply
-- (so the bot picks up DirectApply changes via its polling loop)
CREATE OR REPLACE FUNCTION update_content_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.content_updated_at = NOW();
    ELSIF TG_OP = 'UPDATE' THEN
        IF (OLD.data IS DISTINCT FROM NEW.data) OR
           (OLD.state IS DISTINCT FROM NEW.state AND NEW.state IN ('Draft', 'Pending', 'DirectApply')) THEN
            NEW.content_updated_at = NOW();
        ELSE
            NEW.content_updated_at = OLD.content_updated_at;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
