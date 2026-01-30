-- Migration: Flight Reschedule Notifications
-- When a flight is rescheduled, all check-ins are cancelled and affected users are notified via Discord DM

-- Create table to queue Discord DMs for flight reschedule notifications
CREATE TABLE IF NOT EXISTS flight_reschedule_notifications (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    flight_id INTEGER NOT NULL REFERENCES service_flight_instances(id) ON DELETE CASCADE,
    old_departure TIMESTAMPTZ NOT NULL,
    new_departure TIMESTAMPTZ NOT NULL,
    service_title TEXT NOT NULL,
    sent BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Index for efficient querying of pending notifications
CREATE INDEX IF NOT EXISTS idx_reschedule_notifications_pending
    ON flight_reschedule_notifications(sent, created_at) WHERE sent = false;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON flight_reschedule_notifications TO "nexus-users";
GRANT USAGE, SELECT ON SEQUENCE flight_reschedule_notifications_id_seq TO "nexus-users";

-- Grant permissions to bot user
GRANT SELECT, INSERT, UPDATE, DELETE ON flight_reschedule_notifications TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE flight_reschedule_notifications_id_seq TO "nexus-bot";
