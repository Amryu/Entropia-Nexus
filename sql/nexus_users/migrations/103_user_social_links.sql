-- Add social media link fields to user profiles
ALTER TABLE users ADD COLUMN social_discord TEXT;
ALTER TABLE users ADD COLUMN social_youtube TEXT;
ALTER TABLE users ADD COLUMN social_twitch TEXT;
