-- Add rich text content field to announcements for on-site reading
ALTER TABLE announcements ADD COLUMN content_html TEXT;
