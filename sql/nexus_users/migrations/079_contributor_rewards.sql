BEGIN;

-- Reward rules define payout criteria for wiki contributions
CREATE TABLE IF NOT EXISTS reward_rules (
    id serial PRIMARY KEY,
    name text NOT NULL,
    description text,
    category text,
    entities text[],
    change_type change_type,
    data_fields text[],
    min_amount numeric(10,2) NOT NULL,
    max_amount numeric(10,2) NOT NULL,
    contribution_score numeric(10,2),
    active boolean NOT NULL DEFAULT true,
    sort_order integer NOT NULL DEFAULT 0,
    created_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Rewards assigned to approved changes (one reward per change)
CREATE TABLE IF NOT EXISTS contributor_rewards (
    id serial PRIMARY KEY,
    change_id integer NOT NULL REFERENCES changes(id),
    user_id bigint NOT NULL REFERENCES users(id),
    rule_id integer REFERENCES reward_rules(id),
    amount numeric(10,2) NOT NULL,
    contribution_score numeric(10,2),
    note text,
    assigned_by bigint NOT NULL REFERENCES users(id),
    created_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(change_id)
);

-- Payout tracking for in-game payments
CREATE TABLE IF NOT EXISTS contributor_payouts (
    id serial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id),
    amount numeric(10,2) NOT NULL,
    is_bonus boolean NOT NULL DEFAULT false,
    note text,
    created_by bigint NOT NULL REFERENCES users(id),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed')),
    completed_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_contributor_rewards_user_id ON contributor_rewards(user_id);
CREATE INDEX IF NOT EXISTS idx_contributor_rewards_change_id ON contributor_rewards(change_id);
CREATE INDEX IF NOT EXISTS idx_contributor_payouts_user_id ON contributor_payouts(user_id);
CREATE INDEX IF NOT EXISTS idx_contributor_payouts_status ON contributor_payouts(status);
CREATE INDEX IF NOT EXISTS idx_reward_rules_active ON reward_rules(active);

-- Seed reward rules from bounty program
INSERT INTO reward_rules (name, description, category, entities, change_type, data_fields, min_amount, max_amount, sort_order) VALUES
    ('Add mob spawn', 'Add a new mob spawn area with polygon, all spawnable maturities, and proper flags', 'Mapping', '{Area}', 'Create', NULL, 2.00, 2.00, 1),
    ('Correct mob spawn', 'Fix discrepancies in existing mob spawn areas (amount based on scope of correction)', 'Mapping', '{Area}', 'Update', NULL, 0.25, 2.00, 2),
    ('Add missing location', 'Add teleporters, camps, NPCs, and other relevant locations with proper types', 'Mapping', '{Location}', 'Create', NULL, 0.25, 0.25, 3),
    ('Add/Update item', 'Add or update an item in the database. Recently discovered items award the full amount. Item series (e.g. ArMatrix 10, 15, 20) will only pay up to 40% of the value.', 'Item Data', NULL, NULL, NULL, 0.10, 0.50, 3),
    ('First tiering data', 'Be the first to provide tiering data to an item', 'Item Data', '{Weapon,ArmorSet,MedicalTool,Finder,Excavator}', 'Update', '{Tiers}', 0.50, 0.50, 4),
    ('Add decay values', 'Provide decay values for weapons and tools (proper fruit testing required)', 'Item Data', '{Weapon,MedicalTool,MedicalChip,Refiner,Scanner,Finder,Excavator,TeleportChip,EffectChip,MiscTool,WeaponAmplifier,WeaponVisionAttachment,FinderAmplifier,Vehicle}', 'Update', '{Decay}', 0.50, 0.50, 5),
    ('Add Mob', 'Add a new mob with basic properties, maturities and loot coverage. Mob Areas, Damage Types etc. are paid on top.', 'Mob Data', '{Mob}', 'Create', NULL, 1.50, 1.50, 5),
    ('Mob damage types', 'Provide damage type data for mobs (proper testing documentation required)', 'Mob Data', '{Mob}', 'Update', '{Maturities}', 5.00, 5.00, 6),
    ('Other mob stats', 'Provide other combat stats for mobs (based on coverage)', 'Mob Data', '{Mob}', 'Update', NULL, 0.10, 0.50, 7),
    ('Add/Update Vendor', 'Add or update a vendor with their offers. Specialized vendors and larger inventories pay higher.', 'Information', '{Vendor}', NULL, NULL, 0.50, 5.00, 1)
ON CONFLICT DO NOTHING;

-- Permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON reward_rules TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON contributor_rewards TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON contributor_payouts TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE reward_rules_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE contributor_rewards_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE contributor_payouts_id_seq TO nexus_users;

COMMIT;
