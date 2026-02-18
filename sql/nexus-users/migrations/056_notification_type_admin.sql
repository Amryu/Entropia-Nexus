-- Add 'Admin' notification type for admin review notifications
ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'Admin';
