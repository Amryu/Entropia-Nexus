-- ===========================================================================
-- Entropia Nexus — nexus_users database initial schema
-- ===========================================================================
-- This script creates the nexus_users database schema as it existed BEFORE
-- any migrations were applied.  Run migrations in order after this script.
--
-- Source: nexus_users_schema.sql (pg_dump, schema-only) stripped back to
--         the pre-migration-001 baseline.
-- ===========================================================================

-- -------------------------------------------
-- Roles (idempotent — skip if they already exist)
-- -------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nexus_users') THEN
        CREATE ROLE nexus_users LOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nexus_bot') THEN
        CREATE ROLE nexus_bot LOGIN;
    END IF;
END
$$;

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

-- -------------------------------------------
-- Enum types (original values only — no migration additions)
-- -------------------------------------------

CREATE TYPE public.change_entity AS ENUM (
    'Weapon',
    'ArmorSet',
    'MedicalTool',
    'MedicalChip',
    'Refiner',
    'Scanner',
    'Finder',
    'Excavator',
    'TeleportChip',
    'EffectChip',
    'MiscTool',
    'WeaponAmplifier',
    'WeaponVisionAttachment',
    'Absorber',
    'FinderAmplifier',
    'ArmorPlating',
    'MindforceImplant',
    'Blueprint',
    'Material',
    'Pet',
    'Consumable',
    'CreatureControlCapsule',
    'Vehicle',
    'Furniture',
    'Decoration',
    'StorageContainer',
    'Sign',
    'Clothing',
    'Mob',
    'Vendor',
    'RefiningRecipe',
    'Shop'
);

CREATE TYPE public.change_state AS ENUM (
    'Draft',
    'Pending',
    'Approved',
    'Denied',
    'Deleted'
);

CREATE TYPE public.change_type AS ENUM (
    'Create',
    'Update',
    'Delete'
);

CREATE TYPE public.trade_offer_type AS ENUM (
    'BUY',
    'SELL'
);

-- -------------------------------------------
-- Functions
-- -------------------------------------------

CREATE FUNCTION public.update_last_update_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.last_update = now();
    RETURN NEW;
END;
$$;

-- -------------------------------------------
-- Tables
-- -------------------------------------------

CREATE TABLE public.users (
    id bigint NOT NULL,
    username text,
    global_name text,
    discriminator text,
    avatar text,
    eu_name text,
    verified boolean DEFAULT false,
    administrator boolean DEFAULT false
);

CREATE TABLE public.sessions (
    user_id bigint NOT NULL,
    session_id text NOT NULL,
    access_token text,
    refresh_token text,
    expires bigint
);

CREATE TABLE public.changes (
    id integer NOT NULL,
    author_id bigint NOT NULL,
    type public.change_type NOT NULL,
    data jsonb,
    state public.change_state DEFAULT 'Draft'::public.change_state NOT NULL,
    entity public.change_entity,
    thread_id bigint,
    last_update timestamp with time zone
);

CREATE SEQUENCE public.changes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.changes_id_seq OWNED BY public.changes.id;

CREATE TABLE public.user_settings (
    user_id integer NOT NULL,
    key text NOT NULL,
    value text
);

CREATE TABLE public.trade_offers (
    id integer NOT NULL,
    user_id integer,
    type public.trade_offer_type,
    item_id integer,
    quantity integer,
    min_quantity integer,
    created timestamp with time zone DEFAULT now(),
    updated timestamp with time zone DEFAULT now(),
    details jsonb
);

CREATE SEQUENCE public.offers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.offers_id_seq OWNED BY public.trade_offers.id;

CREATE TABLE public.shop_inventory_groups (
    shop_id integer,
    name text,
    sort_order integer DEFAULT 0,
    id integer NOT NULL
);

CREATE SEQUENCE public.shop_inventory_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.shop_inventory_groups_id_seq OWNED BY public.shop_inventory_groups.id;

CREATE TABLE public.shop_inventory_items (
    shop_id integer,
    group_id integer,
    item_id integer,
    stack_size integer DEFAULT 1,
    markup numeric(10,2) DEFAULT 100.00,
    sort_order integer DEFAULT 0,
    id integer NOT NULL,
    CONSTRAINT shop_inventory_items_markup_check CHECK ((markup >= (0)::numeric)),
    CONSTRAINT shop_inventory_items_stack_size_check CHECK ((stack_size > 0))
);

CREATE SEQUENCE public.shop_inventory_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.shop_inventory_items_id_seq OWNED BY public.shop_inventory_items.id;

CREATE TABLE public.shop_managers (
    shop_id integer NOT NULL,
    user_id bigint NOT NULL
);

-- -------------------------------------------
-- Sequence defaults
-- -------------------------------------------

ALTER TABLE ONLY public.changes ALTER COLUMN id SET DEFAULT nextval('public.changes_id_seq'::regclass);
ALTER TABLE ONLY public.trade_offers ALTER COLUMN id SET DEFAULT nextval('public.offers_id_seq'::regclass);
ALTER TABLE ONLY public.shop_inventory_groups ALTER COLUMN id SET DEFAULT nextval('public.shop_inventory_groups_id_seq'::regclass);
ALTER TABLE ONLY public.shop_inventory_items ALTER COLUMN id SET DEFAULT nextval('public.shop_inventory_items_id_seq'::regclass);

-- -------------------------------------------
-- Primary keys
-- -------------------------------------------

ALTER TABLE ONLY public.changes
    ADD CONSTRAINT changes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.trade_offers
    ADD CONSTRAINT offers_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (user_id, session_id);

ALTER TABLE ONLY public.shop_inventory_groups
    ADD CONSTRAINT shop_inventory_groups_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.shop_inventory_items
    ADD CONSTRAINT shop_inventory_items_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.shop_managers
    ADD CONSTRAINT shop_managers_pkey PRIMARY KEY (shop_id, user_id);

ALTER TABLE ONLY public.user_settings
    ADD CONSTRAINT user_settings_pkey PRIMARY KEY (user_id, key);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

-- -------------------------------------------
-- Indexes
-- -------------------------------------------

CREATE INDEX shop_inventory_groups_shop_id_idx ON public.shop_inventory_groups USING btree (shop_id);
CREATE INDEX shop_inventory_groups_sort_order_idx ON public.shop_inventory_groups USING btree (shop_id, sort_order);

CREATE INDEX shop_inventory_items_group_id_idx ON public.shop_inventory_items USING btree (group_id);
CREATE INDEX shop_inventory_items_item_id_idx ON public.shop_inventory_items USING btree (item_id);
CREATE INDEX shop_inventory_items_shop_id_idx ON public.shop_inventory_items USING btree (shop_id);
CREATE INDEX shop_inventory_items_sort_order_idx ON public.shop_inventory_items USING btree (group_id, sort_order);

CREATE INDEX shop_managers_shop_id_idx ON public.shop_managers USING btree (shop_id);
CREATE INDEX shop_managers_shop_idx ON public.shop_managers USING btree (shop_id);
CREATE INDEX shop_managers_user_id_idx ON public.shop_managers USING btree (user_id);
CREATE INDEX shop_managers_user_idx ON public.shop_managers USING btree (user_id);

-- -------------------------------------------
-- Foreign keys
-- -------------------------------------------

ALTER TABLE ONLY public.shop_inventory_items
    ADD CONSTRAINT shop_inventory_items_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.shop_inventory_groups(id) ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;

-- -------------------------------------------
-- Triggers
-- -------------------------------------------

CREATE TRIGGER update_last_update_trigger BEFORE INSERT OR UPDATE ON public.changes FOR EACH ROW EXECUTE FUNCTION public.update_last_update_column();

-- -------------------------------------------
-- Permissions
-- -------------------------------------------

-- nexus_users role: full CRUD on all tables, usage on sequences
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nexus_users;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_users;

-- nexus_bot role: no initial grants (added by migration 001+)
