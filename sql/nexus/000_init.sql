-- ==========================================================================
-- Entropia Nexus — Initial Database Schema
-- Database: nexus
-- Description: Game data (items, mobs, locations, skills, professions, etc.)
-- Run this BEFORE any migrations in sql/nexus/migrations/
-- ==========================================================================

-- Roles (idempotent — skip if they already exist)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nexus') THEN
        CREATE ROLE nexus LOGIN;
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
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: AreaType; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."AreaType" AS ENUM (
    'PvpArea',
    'PvpLootArea',
    'MobArea',
    'LandArea',
    'ZoneArea',
    'CityArea',
    'EstateArea',
    'EventArea'
);


--
-- Name: BlueprintType; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."BlueprintType" AS ENUM (
    'Weapon',
    'Textile',
    'Vehicle',
    'Enhancer',
    'Furniture',
    'Tool',
    'Armor',
    'Attachment',
    'Metal Component',
    'Electrical Component',
    'Mechanical Component'
);


--
-- Name: CodexType; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."CodexType" AS ENUM (
    'Mob',
    'MobLooter',
    'Asteroid'
);


--
-- Name: EstateType; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."EstateType" AS ENUM (
    'Apartment',
    'Shop'
);


--
-- Name: MissionObjectiveType; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."MissionObjectiveType" AS ENUM (
    'Visit',
    'Interact',
    'Dialog',
    'KillCount',
    'KillPoints',
    'KillCycle',
    'MineCount',
    'MinePoints',
    'MineCycle',
    'CraftAttempts',
    'CraftSuccesses',
    'HandIn'
);


--
-- Name: MissionRewardType; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."MissionRewardType" AS ENUM (
    'Skill',
    'Item',
    'Unlock',
    'None'
);


--
-- Name: MissionType; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."MissionType" AS ENUM (
    'Hunting',
    'Mining',
    'Construction',
    'Dialog',
    'Mixed'
);


--
-- Name: MobType; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."MobType" AS ENUM (
    'Animal',
    'Mutant',
    'Robot',
    'Asteroid'
);


--
-- Name: Shape; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."Shape" AS ENUM (
    'Circle',
    'Rectangle',
    'Polygon'
);


--
-- Name: StrongboxLootRarity; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."StrongboxLootRarity" AS ENUM (
    'Common',
    'Uncommon',
    'Rare',
    'Epic',
    'Supreme',
    'Legendary',
    'Mythical'
);


--
-- Name: VehicleType; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."VehicleType" AS ENUM (
    'Land',
    'Air',
    'Sea',
    'Amphibious',
    'Space'
);


--
-- Name: Absorbers_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Absorbers_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Absorbers_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Absorbers_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Absorbers_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Areas_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Areas_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Areas_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Areas_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Areas_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: ArmorPlatings_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."ArmorPlatings_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "ArmorPlatings_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "ArmorPlatings_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "ArmorPlatings_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: ArmorSets_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."ArmorSets_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "ArmorSets_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "ArmorSets_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "ArmorSets_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Armors_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Armors_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Armors_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Armors_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Armors_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: BlueprintBooks_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."BlueprintBooks_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "BlueprintBooks_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "BlueprintBooks_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "BlueprintBooks_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: BlueprintDrops_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."BlueprintDrops_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "BlueprintDrops_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "BlueprintDrops_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "BlueprintDrops_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: BlueprintMaterials_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."BlueprintMaterials_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "BlueprintMaterials_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "BlueprintMaterials_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "BlueprintMaterials_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: BlueprintTypes_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."BlueprintTypes_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "BlueprintTypes_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "BlueprintTypes_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "BlueprintTypes_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Blueprints_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Blueprints_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Blueprints_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Blueprints_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Blueprints_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Clothes_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Clothes_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Clothes_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Clothes_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Clothes_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Consumables_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Consumables_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Consumables_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Consumables_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Consumables_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: CreatureControlCapsules_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."CreatureControlCapsules_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "CreatureControlCapsules_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "CreatureControlCapsules_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "CreatureControlCapsules_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Decorations_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Decorations_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Decorations_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Decorations_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Decorations_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: EffectChips_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."EffectChips_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "EffectChips_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "EffectChips_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "EffectChips_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: EffectsOnConsume_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."EffectsOnConsume_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "EffectsOnConsume_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "EffectsOnConsume_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "EffectsOnConsume_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: EffectsOnEquip_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."EffectsOnEquip_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "EffectsOnEquip_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "EffectsOnEquip_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "EffectsOnEquip_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: EffectsOnSetEquip_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."EffectsOnSetEquip_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "EffectsOnSetEquip_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "EffectsOnSetEquip_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "EffectsOnSetEquip_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: EffectsOnUse_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."EffectsOnUse_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "EffectsOnUse_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "EffectsOnUse_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "EffectsOnUse_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Effects_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Effects_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Effects_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Effects_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Effects_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: EnhancerType_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."EnhancerType_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "EnhancerType_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "EnhancerType_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "EnhancerType_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: EquipSetItems_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."EquipSetItems_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "EquipSetItems_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "EquipSetItems_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "EquipSetItems_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: EquipSets_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."EquipSets_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "EquipSets_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "EquipSets_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "EquipSets_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: EstateSections_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."EstateSections_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "EstateSections_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "EstateSections_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "EstateSections_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Estates_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Estates_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Estates_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Estates_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Estates_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Excavators_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Excavators_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Excavators_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Excavators_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Excavators_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: FinderAmplifiers_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."FinderAmplifiers_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "FinderAmplifiers_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "FinderAmplifiers_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "FinderAmplifiers_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Finders_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Finders_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Finders_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Finders_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Finders_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Furniture_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Furniture_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Furniture_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Furniture_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Furniture_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Materials_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Materials_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Materials_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Materials_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Materials_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MedicalChips_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MedicalChips_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MedicalChips_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MedicalChips_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MedicalChips_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MedicalTools_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MedicalTools_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MedicalTools_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MedicalTools_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MedicalTools_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MindforceImplants_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MindforceImplants_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MindforceImplants_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MindforceImplants_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MindforceImplants_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MiscTools_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MiscTools_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MiscTools_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MiscTools_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MiscTools_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MissionChains_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MissionChains_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MissionChains_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MissionChains_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MissionChains_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MissionObjectives_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MissionObjectives_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MissionObjectives_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MissionObjectives_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MissionObjectives_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MissionPrerequisites_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MissionPrerequisites_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MissionPrerequisites_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MissionPrerequisites_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MissionPrerequisites_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MissionRewards_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MissionRewards_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MissionRewards_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MissionRewards_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MissionRewards_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Missions_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Missions_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Missions_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Missions_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Missions_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MobAttacks_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MobAttacks_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MobAttacks_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MobAttacks_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MobAttacks_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MobLoots_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MobLoots_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MobLoots_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MobLoots_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MobLoots_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MobMaturities_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MobMaturities_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MobMaturities_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MobMaturities_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MobMaturities_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MobSpawnMaturities_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MobSpawnMaturities_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MobSpawnMaturities_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MobSpawnMaturities_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MobSpawnMaturities_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MobSpawns_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MobSpawns_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MobSpawns_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MobSpawns_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MobSpawns_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: MobSpecies_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."MobSpecies_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "MobSpecies_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "MobSpecies_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "MobSpecies_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Mobs_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Mobs_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Mobs_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Mobs_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Mobs_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Npcs_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Npcs_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Npcs_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Npcs_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Npcs_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: PetEffects_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."PetEffects_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "PetEffects_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "PetEffects_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "PetEffects_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Pets_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Pets_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Pets_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Pets_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Pets_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Planets_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Planets_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Planets_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Planets_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Planets_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: ProfessionCategories_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."ProfessionCategories_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "ProfessionCategories_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "ProfessionCategories_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "ProfessionCategories_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: ProfessionSkills_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."ProfessionSkills_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "ProfessionSkills_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "ProfessionSkills_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "ProfessionSkills_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Professions_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Professions_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Professions_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Professions_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Professions_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Refiners_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Refiners_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Refiners_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Refiners_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Refiners_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: RefiningIngredients_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."RefiningIngredients_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "RefiningIngredients_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "RefiningIngredients_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "RefiningIngredients_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: RefiningRecipes_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."RefiningRecipes_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "RefiningRecipes_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "RefiningRecipes_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "RefiningRecipes_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Scanners_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Scanners_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Scanners_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Scanners_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Scanners_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: ShopInventoryGroups_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."ShopInventoryGroups_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "ShopInventoryGroups_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "ShopInventoryGroups_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "ShopInventoryGroups_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: ShopInventoryItems_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."ShopInventoryItems_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "ShopInventoryItems_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "ShopInventoryItems_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "ShopInventoryItems_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Shops_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Shops_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Shops_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Shops_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Shops_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Signs_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Signs_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Signs_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Signs_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Signs_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: SkillCategories_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."SkillCategories_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "SkillCategories_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "SkillCategories_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "SkillCategories_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: SkillUnlocks_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."SkillUnlocks_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "SkillUnlocks_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "SkillUnlocks_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "SkillUnlocks_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Skills_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Skills_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Skills_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Skills_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Skills_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: StorageContainers_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."StorageContainers_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "StorageContainers_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "StorageContainers_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "StorageContainers_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: StrongboxLoots_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."StrongboxLoots_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "StrongboxLoots_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "StrongboxLoots_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "StrongboxLoots_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Strongboxes_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Strongboxes_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Strongboxes_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Strongboxes_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Strongboxes_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: TeleportationChips_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."TeleportationChips_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "TeleportationChips_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "TeleportationChips_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "TeleportationChips_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Teleporters_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Teleporters_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Teleporters_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Teleporters_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Teleporters_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: TierMaterials_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."TierMaterials_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "TierMaterials_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "TierMaterials_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "TierMaterials_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Tiers_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Tiers_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Tiers_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Tiers_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Tiers_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: VehicleAttachmentSlots_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."VehicleAttachmentSlots_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "VehicleAttachmentSlots_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "VehicleAttachmentSlots_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "VehicleAttachmentSlots_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: VehicleAttachmentTypes_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."VehicleAttachmentTypes_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "VehicleAttachmentTypes_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "VehicleAttachmentTypes_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "VehicleAttachmentTypes_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Vehicles_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Vehicles_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Vehicles_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Vehicles_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Vehicles_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: VendorOfferPrices_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."VendorOfferPrices_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "VendorOfferPrices_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "VendorOfferPrices_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "VendorOfferPrices_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: VendorOffers_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."VendorOffers_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "VendorOffers_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "VendorOffers_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "VendorOffers_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Vendors_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Vendors_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Vendors_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Vendors_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Vendors_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: WeaponAmplifiers_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."WeaponAmplifiers_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "WeaponAmplifiers_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "WeaponAmplifiers_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "WeaponAmplifiers_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: WeaponVisionAttachments_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."WeaponVisionAttachments_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "WeaponVisionAttachments_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "WeaponVisionAttachments_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "WeaponVisionAttachments_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: Weapons_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public."Weapons_audit_trigger"() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
         BEGIN
            IF (TG_OP = 'DELETE') THEN
               INSERT INTO "Weapons_audit" SELECT 'D', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = 'UPDATE') THEN
               INSERT INTO "Weapons_audit" SELECT 'U', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
               INSERT INTO "Weapons_audit" SELECT 'I', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $$;


--
-- Name: furthest_point(jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.furthest_point(vertices_json jsonb) RETURNS TABLE(x numeric, y numeric)
    LANGUAGE plpgsql
    AS $$
DECLARE
  geom GEOMETRY;
  circle RECORD;
BEGIN
  -- Convert the JSONB array of vertices to a LINESTRING geometry
  WITH linestring AS (
    SELECT ST_MakeLine(ARRAY_AGG(ST_MakePoint((vertices_json->'vertices'->>i)::NUMERIC, (vertices_json->'vertices'->>i+1)::NUMERIC))) AS geom
    FROM generate_series(0, JSONB_ARRAY_LENGTH(vertices_json->'vertices') - 2, 2) AS i
  ),
  -- Convert the LINESTRING to a POLYGON
  polygon AS (
    SELECT ST_MakePolygon(l.geom) AS geom
    FROM linestring l
  )
  SELECT p.geom INTO geom FROM polygon p;

  -- Find the largest inscribed circle
  SELECT (ST_MaximumInscribedCircle(geom)).* INTO circle;

  -- Assign the center coordinates to the output columns
  x := ST_X(circle.center);
  y := ST_Y(circle.center);

  RETURN QUERY SELECT x, y;
END;
$$;


--
-- Name: shops_audit_trigger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.shops_audit_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO public.shops_audit (
            id, name, planet_id, longitude, latitude, altitude, description, 
            owner_id, created_at, updated_at, audit_action, audit_user
        ) VALUES (
            OLD.id, OLD.name, OLD.planet_id, OLD.longitude, OLD.latitude, OLD.altitude, OLD.description,
            OLD.owner_id, OLD.created_at, OLD.updated_at, 'DELETE', current_user
        );
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO public.shops_audit (
            id, name, planet_id, longitude, latitude, altitude, description,
            owner_id, created_at, updated_at, audit_action, audit_user
        ) VALUES (
            NEW.id, NEW.name, NEW.planet_id, NEW.longitude, NEW.latitude, NEW.altitude, NEW.description,
            NEW.owner_id, NEW.created_at, NEW.updated_at, 'UPDATE', current_user
        );
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' THEN
        INSERT INTO public.shops_audit (
            id, name, planet_id, longitude, latitude, altitude, description,
            owner_id, created_at, updated_at, audit_action, audit_user
        ) VALUES (
            NEW.id, NEW.name, NEW.planet_id, NEW.longitude, NEW.latitude, NEW.altitude, NEW.description,
            NEW.owner_id, NEW.created_at, NEW.updated_at, 'INSERT', current_user
        );
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$;


--
-- Name: update_coordinates(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_coordinates() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  x NUMERIC;
  y NUMERIC;
  data JSONB;
BEGIN
  data := NEW."Data";

  IF NEW."Shape" = 'Circle' THEN
    x := (data->>'x')::NUMERIC;
    y := (data->>'y')::NUMERIC;
  ELSIF NEW."Shape" = 'Rectangle' THEN
    x := ((data->>'x')::NUMERIC + (data->>'width')::NUMERIC / 2);
    y := ((data->>'y')::NUMERIC + (data->>'height')::NUMERIC / 2);
  ELSIF NEW."Shape" = 'Polygon' THEN
    SELECT * INTO x, y FROM furthest_point(data);
  END IF;

  NEW."Longitude" := x;
  NEW."Latitude" := y;

  RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: Absorbers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Absorbers" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Weight" numeric,
    "Absorption" numeric,
    "Decay" numeric,
    "MaxTT" integer,
    "MinTT" integer,
    "Efficiency" integer,
    "Description" text
);


--
-- Name: Absorbers_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Absorbers_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Absorbers_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Absorbers_Id_seq" OWNED BY public."Absorbers"."Id";


--
-- Name: Absorbers_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Absorbers_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Weight" numeric,
    "Absorption" numeric,
    "MaxTT" integer,
    "MinTT" integer,
    "Efficiency" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Absorbers");


--
-- Name: Areas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Areas" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Type" public."AreaType" NOT NULL,
    "Shape" public."Shape" NOT NULL,
    "Data" jsonb NOT NULL,
    "Longitude" integer,
    "Latitude" integer,
    "Altitude" integer,
    "PlanetId" integer,
    "TechnicalId" text
);


--
-- Name: Areas_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Areas_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Areas_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Areas_Id_seq" OWNED BY public."Areas"."Id";


--
-- Name: Areas_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Areas_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Type" public."AreaType",
    "Shape" public."Shape",
    "Data" jsonb,
    "Longitude" integer,
    "Latitude" integer,
    "Altitude" integer,
    "PlanetId" integer,
    "TechnicalId" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL,
    "Description" text
)
INHERITS (public."Areas");


--
-- Name: ArmorPlatings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."ArmorPlatings" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Weight" numeric,
    "Stab" numeric,
    "Cut" numeric,
    "Impact" numeric,
    "Penetration" numeric,
    "Shrapnel" numeric,
    "Burn" numeric,
    "Cold" numeric,
    "Acid" numeric,
    "Electric" numeric,
    "Durability" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Block" numeric,
    "Description" text
);


--
-- Name: ArmorPlatings_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."ArmorPlatings_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ArmorPlatings_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."ArmorPlatings_Id_seq" OWNED BY public."ArmorPlatings"."Id";


--
-- Name: ArmorPlatings_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."ArmorPlatings_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Weight" numeric,
    "Stab" numeric,
    "Cut" numeric,
    "Impact" numeric,
    "Penetration" numeric,
    "Shrapnel" numeric,
    "Burn" numeric,
    "Cold" numeric,
    "Acid" numeric,
    "Electric" numeric,
    "Durability" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Block" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."ArmorPlatings");


--
-- Name: ArmorSets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."ArmorSets" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Durability" integer,
    "Stab" integer,
    "Cut" integer,
    "Impact" integer,
    "Penetration" integer,
    "Shrapnel" integer,
    "Burn" integer,
    "Cold" integer,
    "Acid" integer,
    "Electric" integer,
    "PlanetId" integer,
    "Description" text
);


--
-- Name: ArmorSets_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."ArmorSets_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ArmorSets_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."ArmorSets_Id_seq" OWNED BY public."ArmorSets"."Id";


--
-- Name: ArmorSets_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."ArmorSets_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Durability" integer,
    "Stab" integer,
    "Cut" integer,
    "Impact" integer,
    "Penetration" integer,
    "Shrapnel" integer,
    "Burn" integer,
    "Cold" integer,
    "Acid" integer,
    "Electric" integer,
    "PlanetId" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."ArmorSets");


--
-- Name: Armors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Armors" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "SetId" integer NOT NULL,
    "Weight" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Gender" text DEFAULT 'Both'::text,
    "Slot" text,
    "Description" text
);


--
-- Name: Armors_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Armors_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Armors_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Armors_Id_seq" OWNED BY public."Armors"."Id";


--
-- Name: Armors_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Armors_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "SetId" integer,
    "Weight" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Gender" text DEFAULT NULL,
    "Slot" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Armors");


--
-- Name: EnhancerType; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EnhancerType" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Tool" text NOT NULL,
    "Value" numeric
);


--
-- Name: Enhancers; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public."Enhancers" AS
 WITH RECURSIVE cnt(x) AS (
         SELECT 1 AS "?column?"
        UNION ALL
         SELECT (cnt_1.x + 1)
           FROM cnt cnt_1
          WHERE (cnt_1.x < 10)
        )
 SELECT ((("EnhancerType"."Id" * 10) + cnt.x) - 10) AS "Id",
    (((("EnhancerType"."Tool" || ' '::text) || "EnhancerType"."Name") || ' Enhancer '::text) || cnt.x) AS "Name",
    "EnhancerType"."Id" AS "TypeId",
    cnt.x AS "Socket",
    0.01 AS "Weight",
    "EnhancerType"."Value"
   FROM (ONLY public."EnhancerType"
     JOIN cnt ON (true));


--
-- Name: FinderAmplifiers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."FinderAmplifiers" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Weight" numeric,
    "Efficiency" numeric,
    "Decay" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "ProfessionMinimum" numeric,
    "Description" text
);


--
-- Name: MindforceImplants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MindforceImplants" (
    "Id" integer NOT NULL,
    "Name" text,
    "Weight" numeric,
    "MaxLvl" integer,
    "Absorption" double precision,
    "MinTT" numeric,
    "MaxTT" numeric,
    "Description" text
);


--
-- Name: WeaponAmplifiers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."WeaponAmplifiers" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Type" text,
    "Weight" numeric,
    "Decay" numeric,
    "Ammo" integer,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Efficiency" numeric,
    "Stab" numeric,
    "Cut" numeric,
    "Impact" numeric,
    "Penetration" numeric,
    "Shrapnel" numeric,
    "Burn" numeric,
    "Cold" numeric,
    "Acid" numeric,
    "Electric" numeric,
    "Absorption" numeric,
    "Description" text
);


--
-- Name: WeaponVisionAttachments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."WeaponVisionAttachments" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Type" text,
    "Weight" numeric,
    "SkillMod" numeric,
    "SkillBonus" numeric,
    "Zoom" numeric,
    "Decay" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Efficiency" numeric,
    "Description" text
);


--
-- Name: Attachments; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public."Attachments" AS
 SELECT ("WeaponAmplifiers"."Id" + 100000) AS "Id",
    "WeaponAmplifiers"."Name",
    "WeaponAmplifiers"."MaxTT",
    "WeaponAmplifiers"."Weight",
    'WeaponAmplifier'::text AS "Type"
   FROM ONLY public."WeaponAmplifiers"
UNION ALL
 SELECT ("WeaponVisionAttachments"."Id" + 200000) AS "Id",
    "WeaponVisionAttachments"."Name",
    "WeaponVisionAttachments"."MaxTT",
    "WeaponVisionAttachments"."Weight",
    'WeaponVisionAttachment'::text AS "Type"
   FROM ONLY public."WeaponVisionAttachments"
UNION ALL
 SELECT ("Absorbers"."Id" + 300000) AS "Id",
    "Absorbers"."Name",
    "Absorbers"."MaxTT",
    "Absorbers"."Weight",
    'Absorber'::text AS "Type"
   FROM ONLY public."Absorbers"
UNION ALL
 SELECT ("FinderAmplifiers"."Id" + 400000) AS "Id",
    "FinderAmplifiers"."Name",
    "FinderAmplifiers"."MaxTT",
    "FinderAmplifiers"."Weight",
    'FinderAmplifier'::text AS "Type"
   FROM ONLY public."FinderAmplifiers"
UNION ALL
 SELECT ("ArmorPlatings"."Id" + 500000) AS "Id",
    "ArmorPlatings"."Name",
    "ArmorPlatings"."MaxTT",
    "ArmorPlatings"."Weight",
    'ArmorPlating'::text AS "Type"
   FROM ONLY public."ArmorPlatings"
UNION ALL
 SELECT ("Enhancers"."Id" + 600000) AS "Id",
    "Enhancers"."Name",
    "Enhancers"."Value" AS "MaxTT",
    "Enhancers"."Weight",
    'Enhancer'::text AS "Type"
   FROM ONLY public."Enhancers"
UNION ALL
 SELECT ("MindforceImplants"."Id" + 700000) AS "Id",
    "MindforceImplants"."Name",
    "MindforceImplants"."MaxTT",
    "MindforceImplants"."Weight",
    'MindforceImplant'::text AS "Type"
   FROM ONLY public."MindforceImplants";


--
-- Name: BlueprintBooks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."BlueprintBooks" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Weight" numeric,
    "Value" numeric,
    "PlanetId" integer,
    "Description" text
);


--
-- Name: BlueprintBooks_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."BlueprintBooks_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: BlueprintBooks_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."BlueprintBooks_Id_seq" OWNED BY public."BlueprintBooks"."Id";


--
-- Name: BlueprintBooks_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."BlueprintBooks_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Weight" numeric,
    "Value" numeric,
    "PlanetId" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."BlueprintBooks");


--
-- Name: BlueprintDrops; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."BlueprintDrops" (
    "SourceId" integer NOT NULL,
    "DropId" integer NOT NULL
);


--
-- Name: BlueprintDrops_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."BlueprintDrops_audit" (
    "SourceId" integer,
    "DropId" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."BlueprintDrops");


--
-- Name: BlueprintMaterials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."BlueprintMaterials" (
    "BlueprintId" integer NOT NULL,
    "ItemId" integer NOT NULL,
    "Amount" integer
);


--
-- Name: BlueprintMaterials_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."BlueprintMaterials_audit" (
    "BlueprintId" integer,
    "ItemId" integer,
    "Amount" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."BlueprintMaterials");


--
-- Name: BlueprintTypes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."BlueprintTypes" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL
);


--
-- Name: BlueprintTypes_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."BlueprintTypes_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: BlueprintTypes_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."BlueprintTypes_Id_seq" OWNED BY public."BlueprintTypes"."Id";


--
-- Name: BlueprintTypes_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."BlueprintTypes_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."BlueprintTypes");


--
-- Name: Blueprints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Blueprints" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Level" integer,
    "TypeId" integer,
    "ItemId" integer,
    "ProfessionId" integer,
    "BookId" integer,
    "MinLvl" numeric,
    "MaxLvl" numeric,
    "IsSib" integer,
    "IsBoosted" integer,
    "MinimumCraftAmount" integer DEFAULT 1,
    "MaximumCraftAmount" integer,
    "Type" public."BlueprintType",
    "Description" text
);


--
-- Name: Blueprints_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Blueprints_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Blueprints_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Blueprints_Id_seq" OWNED BY public."Blueprints"."Id";


--
-- Name: Blueprints_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Blueprints_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Level" integer,
    "TypeId" integer,
    "ItemId" integer,
    "ProfessionId" integer,
    "BookId" integer,
    "MinLvl" numeric,
    "MaxLvl" numeric,
    "IsSib" integer,
    "IsBoosted" integer,
    "MinimumCraftAmount" integer DEFAULT NULL,
    "MaximumCraftAmount" integer,
    "Type" public."BlueprintType",
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Blueprints");


--
-- Name: Clothes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Clothes" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Gender" text,
    "Type" text,
    "Weight" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Slot" text,
    "Description" text
);


--
-- Name: Clothes_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Clothes_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Clothes_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Clothes_Id_seq" OWNED BY public."Clothes"."Id";


--
-- Name: Clothes_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Clothes_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Gender" text,
    "Type" text,
    "Weight" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Slot" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Clothes");


--
-- Name: Consumables; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Consumables" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Type" text,
    "Weight" numeric,
    "Value" numeric,
    "Description" text
);


--
-- Name: Consumables_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Consumables_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Consumables_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Consumables_Id_seq" OWNED BY public."Consumables"."Id";


--
-- Name: Consumables_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Consumables_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Type" text,
    "Weight" numeric,
    "Value" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Consumables");


--
-- Name: CreatureControlCapsules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."CreatureControlCapsules" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "MobId" integer,
    "Weight" numeric,
    "MaxTT" numeric,
    "ScanningProfessionId" integer,
    "ProfessionLevel" numeric,
    "Description" text
);


--
-- Name: CreatureControlCapsules_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."CreatureControlCapsules_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: CreatureControlCapsules_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."CreatureControlCapsules_Id_seq" OWNED BY public."CreatureControlCapsules"."Id";


--
-- Name: CreatureControlCapsules_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."CreatureControlCapsules_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "MobId" integer,
    "Weight" numeric,
    "MaxTT" numeric,
    "ScanningProfessionId" integer,
    "ProfessionLevel" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."CreatureControlCapsules");


--
-- Name: Decorations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Decorations" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Type" text,
    "Weight" numeric,
    "MaxTT" numeric,
    "Description" text
);


--
-- Name: Decorations_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Decorations_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Decorations_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Decorations_Id_seq" OWNED BY public."Decorations"."Id";


--
-- Name: Decorations_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Decorations_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Type" text,
    "Weight" numeric,
    "MaxTT" numeric,
    "Description" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Decorations");


--
-- Name: EffectChips; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EffectChips" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Level" integer,
    "Weight" numeric,
    "Type" text,
    "Duration" numeric,
    "Strength" numeric,
    "Concentration" numeric,
    "CooldownGroup" integer,
    "Range" numeric,
    "Uses" integer,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Decay" numeric,
    "AmmoId" integer,
    "AmmoBurn" integer,
    "ProfessionId" integer,
    "MinLevel" numeric,
    "MaxLevel" numeric,
    "Cooldown" numeric,
    "IsSib" integer,
    "Description" text
);


--
-- Name: EffectChips_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."EffectChips_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: EffectChips_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."EffectChips_Id_seq" OWNED BY public."EffectChips"."Id";


--
-- Name: EffectChips_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EffectChips_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Level" integer,
    "Weight" numeric,
    "Type" text,
    "Duration" numeric,
    "Strength" numeric,
    "Concentration" numeric,
    "CooldownGroup" integer,
    "Range" numeric,
    "Uses" integer,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Decay" numeric,
    "AmmoId" integer,
    "AmmoBurn" integer,
    "ProfessionId" integer,
    "MinLevel" numeric,
    "MaxLevel" numeric,
    "Cooldown" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."EffectChips");


--
-- Name: Effects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Effects" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Unit" text,
    "IsPositive" integer,
    "LimitAction" numeric,
    "LimitItem" numeric,
    "LimitTotal" numeric,
    "Description" text
);


--
-- Name: EffectsOnConsume; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EffectsOnConsume" (
    "ConsumableId" integer NOT NULL,
    "EffectId" integer NOT NULL,
    "DurationSeconds" integer,
    "Strength" numeric
);


--
-- Name: EffectsOnConsume_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EffectsOnConsume_audit" (
    "ConsumableId" integer,
    "EffectId" integer,
    "DurationSeconds" integer,
    "Strength" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."EffectsOnConsume");


--
-- Name: EffectsOnEquip; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EffectsOnEquip" (
    "ItemId" integer NOT NULL,
    "EffectId" integer NOT NULL,
    "Strength" numeric
);


--
-- Name: EffectsOnEquip_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EffectsOnEquip_audit" (
    "ItemId" integer,
    "EffectId" integer,
    "Strength" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."EffectsOnEquip");


--
-- Name: EffectsOnSetEquip; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EffectsOnSetEquip" (
    "SetId" integer NOT NULL,
    "EffectId" integer NOT NULL,
    "MinSetPieces" integer NOT NULL,
    "Strength" numeric
);


--
-- Name: EffectsOnSetEquip_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EffectsOnSetEquip_audit" (
    "SetId" integer,
    "EffectId" integer,
    "MinSetPieces" integer,
    "Strength" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."EffectsOnSetEquip");


--
-- Name: EffectsOnUse; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EffectsOnUse" (
    "ItemId" integer NOT NULL,
    "EffectId" integer NOT NULL,
    "Strength" numeric,
    "DurationSeconds" integer,
    "IsSelfTarget" integer DEFAULT 0
);


--
-- Name: EffectsOnUse_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EffectsOnUse_audit" (
    "ItemId" integer,
    "EffectId" integer,
    "Strength" numeric,
    "DurationSeconds" integer,
    "IsSelfTarget" integer DEFAULT NULL,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."EffectsOnUse");


--
-- Name: Effects_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Effects_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Effects_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Effects_Id_seq" OWNED BY public."Effects"."Id";


--
-- Name: Effects_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Effects_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Unit" text,
    "IsPositive" integer,
    "LimitAction" numeric,
    "LimitItem" numeric,
    "LimitTotal" numeric,
    "Description" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Effects");


--
-- Name: EnhancerType_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."EnhancerType_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: EnhancerType_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."EnhancerType_Id_seq" OWNED BY public."EnhancerType"."Id";


--
-- Name: EnhancerType_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EnhancerType_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Tool" text,
    "Value" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."EnhancerType");


--
-- Name: EquipSetItems; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EquipSetItems" (
    "EquipSetId" integer NOT NULL,
    "ItemId" integer NOT NULL
);


--
-- Name: EquipSetItems_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EquipSetItems_audit" (
    "EquipSetId" integer,
    "ItemId" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."EquipSetItems");


--
-- Name: EquipSets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EquipSets" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL
);


--
-- Name: EquipSets_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."EquipSets_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: EquipSets_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."EquipSets_Id_seq" OWNED BY public."EquipSets"."Id";


--
-- Name: EquipSets_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EquipSets_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."EquipSets");


--
-- Name: EstateSections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EstateSections" (
    "EstateId" integer NOT NULL,
    "Name" text NOT NULL,
    "Description" text,
    "ItemPoints" integer
);


--
-- Name: EstateSections_EstateId_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."EstateSections_EstateId_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: EstateSections_EstateId_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."EstateSections_EstateId_seq" OWNED BY public."EstateSections"."EstateId";


--
-- Name: EstateSections_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."EstateSections_audit" (
    "EstateId" integer DEFAULT NULL,
    "Name" text,
    "Description" text,
    "ItemPoints" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."EstateSections");


--
-- Name: Estates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Estates" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Description" text,
    "Longitude" integer,
    "Latitude" integer,
    "Altitude" integer,
    "PlanetId" integer,
    "Type" public."EstateType",
    "OwnerId" integer,
    "ItemTradeAvailable" boolean,
    "MaxGuests" integer
);


--
-- Name: Estates_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Estates_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Estates_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Estates_Id_seq" OWNED BY public."Estates"."Id";


--
-- Name: Estates_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Estates_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Description" text,
    "Longitude" integer,
    "Latitude" integer,
    "Altitude" integer,
    "PlanetId" integer,
    "Type" public."EstateType",
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Estates");


--
-- Name: Excavators; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Excavators" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Weight" numeric,
    "Uses" integer,
    "Efficiency" numeric,
    "Decay" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "IntervalStart" numeric,
    "IntervalEnd" numeric,
    "Description" text
);


--
-- Name: Excavators_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Excavators_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Excavators_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Excavators_Id_seq" OWNED BY public."Excavators"."Id";


--
-- Name: Excavators_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Excavators_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Weight" numeric,
    "Uses" integer,
    "Efficiency" numeric,
    "Decay" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "IntervalStart" numeric,
    "IntervalEnd" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Excavators");


--
-- Name: FinderAmplifiers_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."FinderAmplifiers_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: FinderAmplifiers_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."FinderAmplifiers_Id_seq" OWNED BY public."FinderAmplifiers"."Id";


--
-- Name: FinderAmplifiers_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."FinderAmplifiers_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Weight" numeric,
    "Efficiency" numeric,
    "Decay" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "ProfessionMinimum" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."FinderAmplifiers");


--
-- Name: Finders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Finders" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Weight" numeric,
    "Range" numeric,
    "Depth" numeric,
    "Uses" integer,
    "Decay" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "IntervalStart" numeric,
    "IntervalEnd" numeric,
    "Probes" integer,
    "Description" text
);


--
-- Name: Finders_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Finders_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Finders_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Finders_Id_seq" OWNED BY public."Finders"."Id";


--
-- Name: Finders_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Finders_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Weight" numeric,
    "Range" numeric,
    "Depth" numeric,
    "Uses" integer,
    "Decay" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "IntervalStart" numeric,
    "IntervalEnd" numeric,
    "Probes" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Finders");


--
-- Name: Furniture; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Furniture" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Type" text,
    "Weight" numeric,
    "MaxTT" numeric,
    "PlanetId" integer,
    "Description" text
);


--
-- Name: Signs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Signs" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Weight" numeric,
    "ItemPoints" integer,
    "AspectRatio" text,
    "LocalContentScreen" integer,
    "ImagesAndText" integer,
    "Effects" integer,
    "Multimedia" integer,
    "ParticipantContent" integer,
    "Cost" numeric,
    "MaxTT" numeric,
    "Description" text
);


--
-- Name: StorageContainers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."StorageContainers" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Weight" numeric,
    "Capacity" integer,
    "MaxWeight" numeric,
    "MaxTT" numeric,
    "PlanetId" integer,
    "Description" text
);


--
-- Name: Furnishings; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public."Furnishings" AS
 SELECT ("Furniture"."Id" + 100000) AS "Id",
    "Furniture"."Name",
    "Furniture"."MaxTT",
    "Furniture"."Weight",
    'Furniture'::text AS "Type"
   FROM ONLY public."Furniture"
UNION ALL
 SELECT ("Decorations"."Id" + 200000) AS "Id",
    "Decorations"."Name",
    "Decorations"."MaxTT",
    "Decorations"."Weight",
    'Decoration'::text AS "Type"
   FROM ONLY public."Decorations"
UNION ALL
 SELECT ("StorageContainers"."Id" + 300000) AS "Id",
    "StorageContainers"."Name",
    "StorageContainers"."MaxTT",
    "StorageContainers"."Weight",
    'StorageContainer'::text AS "Type"
   FROM ONLY public."StorageContainers"
UNION ALL
 SELECT ("Signs"."Id" + 400000) AS "Id",
    "Signs"."Name",
    "Signs"."MaxTT",
    "Signs"."Weight",
    'Sign'::text AS "Type"
   FROM ONLY public."Signs";


--
-- Name: Furniture_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Furniture_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Furniture_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Furniture_Id_seq" OWNED BY public."Furniture"."Id";


--
-- Name: Furniture_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Furniture_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Type" text,
    "Weight" numeric,
    "MaxTT" numeric,
    "PlanetId" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Furniture");


--
-- Name: ItemTags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."ItemTags" (
    "ItemId" integer NOT NULL,
    "TagId" integer NOT NULL
);


--
-- Name: Materials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Materials" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Type" text,
    "Weight" numeric,
    "Stackable" integer,
    "MaxStack" integer DEFAULT 0,
    "Value" numeric,
    "Description" text
);


--
-- Name: MedicalChips; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MedicalChips" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Level" integer,
    "Range" real,
    "Weight" numeric,
    "Heal" numeric,
    "StartInterval" numeric,
    "Uses" integer,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Decay" numeric,
    "AmmoBurn" integer,
    "Concentration" numeric,
    "Cooldown" numeric,
    "CooldownGroup" integer,
    "AmmoId" integer,
    "MinLvl" numeric,
    "MaxLvl" numeric,
    "SIB" integer,
    "Description" text
);


--
-- Name: MedicalTools; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MedicalTools" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Weight" numeric,
    "Heal" numeric,
    "StartInterval" numeric,
    "Uses" integer,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Decay" numeric,
    "MinLvl" numeric,
    "MaxLvl" numeric,
    "SIB" integer,
    "Description" text
);


--
-- Name: MiscTools; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MiscTools" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Type" text,
    "Weight" numeric,
    "Decay" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "ProfessionId" integer,
    "IsSib" integer,
    "MinLevel" numeric,
    "MaxLevel" numeric,
    "Description" text
);


--
-- Name: Pets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Pets" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Rarity" text,
    "Training" text,
    "NutrioCapacity" integer,
    "NutrioConsumption" integer,
    "Exportable" integer,
    "PlanetId" integer,
    "TamingLevel" numeric,
    "Description" text
);


--
-- Name: Refiners; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Refiners" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Weight" integer,
    "Uses" text,
    "Decay" real,
    "MaxTT" real,
    "MinTT" real,
    "Description" text
);


--
-- Name: Scanners; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Scanners" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Weight" integer,
    "Range" integer,
    "Uses" integer,
    "Decay" text,
    "MaxTT" integer,
    "MinTT" text,
    "Description" text
);


--
-- Name: TeleportationChips; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."TeleportationChips" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Level" integer,
    "Weight" numeric,
    "Concentration" numeric,
    "Cooldown" numeric,
    "CooldownGroup" integer,
    "Range" numeric,
    "UsesPerMinute" integer,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Decay" numeric,
    "AmmoId" integer,
    "AmmoBurn" integer,
    "ProfessionId" integer,
    "MinLevel" numeric,
    "MaxLevel" numeric,
    "Description" text
);


--
-- Name: Tools; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public."Tools" AS
 SELECT ("MedicalTools"."Id" + 100000) AS "Id",
    "MedicalTools"."Name",
    "MedicalTools"."MaxTT",
    "MedicalTools"."Weight",
    'MedicalTool'::text AS "Type"
   FROM ONLY public."MedicalTools"
UNION ALL
 SELECT ("MiscTools"."Id" + 200000) AS "Id",
    "MiscTools"."Name",
    "MiscTools"."MaxTT",
    "MiscTools"."Weight",
    'MiscTool'::text AS "Type"
   FROM ONLY public."MiscTools"
UNION ALL
 SELECT ("Refiners"."Id" + 300000) AS "Id",
    "Refiners"."Name",
    "Refiners"."MaxTT",
    "Refiners"."Weight",
    'Refiner'::text AS "Type"
   FROM ONLY public."Refiners"
UNION ALL
 SELECT ("Scanners"."Id" + 400000) AS "Id",
    "Scanners"."Name",
    "Scanners"."MaxTT",
    "Scanners"."Weight",
    'Scanner'::text AS "Type"
   FROM ONLY public."Scanners"
UNION ALL
 SELECT ("Finders"."Id" + 500000) AS "Id",
    "Finders"."Name",
    "Finders"."MaxTT",
    "Finders"."Weight",
    'Finder'::text AS "Type"
   FROM ONLY public."Finders"
UNION ALL
 SELECT ("Excavators"."Id" + 600000) AS "Id",
    "Excavators"."Name",
    "Excavators"."MaxTT",
    "Excavators"."Weight",
    'Excavator'::text AS "Type"
   FROM ONLY public."Excavators"
UNION ALL
 SELECT ("BlueprintBooks"."Id" + 700000) AS "Id",
    "BlueprintBooks"."Name",
    "BlueprintBooks"."Value" AS "MaxTT",
    "BlueprintBooks"."Weight",
    'BlueprintBook'::text AS "Type"
   FROM ONLY public."BlueprintBooks"
UNION ALL
 SELECT ("MedicalChips"."Id" + 800000) AS "Id",
    "MedicalChips"."Name",
    "MedicalChips"."MaxTT",
    "MedicalChips"."Weight",
    'MedicalChip'::text AS "Type"
   FROM ONLY public."MedicalChips"
UNION ALL
 SELECT ("TeleportationChips"."Id" + 810000) AS "Id",
    "TeleportationChips"."Name",
    "TeleportationChips"."MaxTT",
    "TeleportationChips"."Weight",
    'TeleportationChip'::text AS "Type"
   FROM ONLY public."TeleportationChips"
UNION ALL
 SELECT ("EffectChips"."Id" + 820000) AS "Id",
    "EffectChips"."Name",
    "EffectChips"."MaxTT",
    "EffectChips"."Weight",
    'EffectChip'::text AS "Type"
   FROM ONLY public."EffectChips";


--
-- Name: Vehicles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Vehicles" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Passengers" integer,
    "Weight" numeric,
    "SpawnedWeight" numeric,
    "CustomColors" integer,
    "CustomTextures" integer,
    "StorageCount" integer,
    "StorageWeight" numeric,
    "FuelMaterialId" integer,
    "FuelActive" numeric,
    "FuelPassive" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "WheelGrip" numeric,
    "EnginePower" numeric,
    "MaxSpeed" numeric,
    "MaxSI" numeric,
    "Stab" numeric,
    "Cut" numeric,
    "Impact" numeric,
    "Penetration" numeric,
    "Shrapnel" numeric,
    "Burn" numeric,
    "Cold" numeric,
    "Acid" numeric,
    "Electric" numeric,
    "Durability" text,
    "Description" text,
    "Type" public."VehicleType"
);


--
-- Name: Weapons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Weapons" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Class" text,
    "Type" text,
    "MFLevel" integer,
    "Range" numeric,
    "Weight" numeric,
    "ImpactRadius" numeric,
    "Attacks" numeric,
    "Decay" numeric,
    "AmmoBurn" integer,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Efficiency" numeric,
    "Stab" numeric,
    "Cut" numeric,
    "Impact" numeric,
    "Penetration" numeric,
    "Shrapnel" numeric,
    "Burn" numeric,
    "Cold" numeric,
    "Acid" numeric,
    "Electric" numeric,
    "SIB" integer,
    "Concentration" numeric,
    "Cooldown" numeric,
    "CooldownGroup" text,
    "MinHit" numeric,
    "MaxHit" numeric,
    "MinDmg" numeric,
    "MaxDmg" numeric,
    "PlanetId" integer,
    "AttachmentTypeId" integer,
    "AmmoId" integer,
    "ProfessionHitId" integer,
    "ProfessionDmgId" integer,
    "Category" text,
    "Description" text
);


--
-- Name: Items; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public."Items" AS
 SELECT ("Materials"."Id" + 1000000) AS "Id",
    "Materials"."Name",
    "Materials"."Value",
    "Materials"."Weight",
    'Material'::text AS "Type"
   FROM ONLY public."Materials"
UNION ALL
 SELECT ("Weapons"."Id" + 2000000) AS "Id",
    "Weapons"."Name",
    "Weapons"."MaxTT" AS "Value",
    "Weapons"."Weight",
    'Weapon'::text AS "Type"
   FROM ONLY public."Weapons"
UNION ALL
 SELECT ("Armors"."Id" + 3000000) AS "Id",
    "Armors"."Name",
    "Armors"."MaxTT" AS "Value",
    "Armors"."Weight",
    'Armor'::text AS "Type"
   FROM ONLY public."Armors"
UNION ALL
 SELECT ("Tools"."Id" + 4000000) AS "Id",
    "Tools"."Name",
    "Tools"."MaxTT" AS "Value",
    "Tools"."Weight",
    "Tools"."Type"
   FROM ONLY public."Tools"
UNION ALL
 SELECT ("Attachments"."Id" + 5000000) AS "Id",
    "Attachments"."Name",
    "Attachments"."MaxTT" AS "Value",
    "Attachments"."Weight",
    "Attachments"."Type"
   FROM ONLY public."Attachments"
UNION ALL
 SELECT ("Blueprints"."Id" + 6000000) AS "Id",
    "Blueprints"."Name",
    1 AS "Value",
    0.1 AS "Weight",
    'Blueprint'::text AS "Type"
   FROM ONLY public."Blueprints"
UNION ALL
 SELECT ("Vehicles"."Id" + 7000000) AS "Id",
    "Vehicles"."Name",
    "Vehicles"."MaxTT" AS "Value",
    "Vehicles"."Weight",
    'Vehicle'::text AS "Type"
   FROM ONLY public."Vehicles"
UNION ALL
 SELECT ("Clothes"."Id" + 8000000) AS "Id",
    "Clothes"."Name",
    "Clothes"."MaxTT" AS "Value",
    "Clothes"."Weight",
    'Clothing'::text AS "Type"
   FROM ONLY public."Clothes"
UNION ALL
 SELECT ("Furnishings"."Id" + 9000000) AS "Id",
    "Furnishings"."Name",
    "Furnishings"."MaxTT" AS "Value",
    "Furnishings"."Weight",
    "Furnishings"."Type"
   FROM ONLY public."Furnishings"
UNION ALL
 SELECT ("Consumables"."Id" + 10000000) AS "Id",
    "Consumables"."Name",
    "Consumables"."Value",
    "Consumables"."Weight",
    'Consumable'::text AS "Type"
   FROM ONLY public."Consumables"
UNION ALL
 SELECT ("CreatureControlCapsules"."Id" + 10100000) AS "Id",
    "CreatureControlCapsules"."Name",
    "CreatureControlCapsules"."MaxTT" AS "Value",
    "CreatureControlCapsules"."Weight",
    'Capsule'::text AS "Type"
   FROM ONLY public."CreatureControlCapsules"
UNION ALL
 SELECT ("Pets"."Id" + 11000000) AS "Id",
    "Pets"."Name",
    0 AS "Value",
    0 AS "Weight",
    'Pet'::text AS "Type"
   FROM ONLY public."Pets";


--
-- Name: Teleporters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Teleporters" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "PlanetId" integer,
    "Longitude" integer,
    "Latitude" integer,
    "Altitude" integer,
    "Description" text
);


--
-- Name: Locations; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public."Locations" AS
 SELECT ("Teleporters"."Id" + 100000) AS "Id",
    "Teleporters"."Name",
    "Teleporters"."Longitude",
    "Teleporters"."Latitude",
    "Teleporters"."Altitude",
    "Teleporters"."PlanetId",
    'Teleporter'::text AS "Type"
   FROM ONLY public."Teleporters"
UNION ALL
 SELECT ("Areas"."Id" + 200000) AS "Id",
    "Areas"."Name",
    "Areas"."Longitude",
    "Areas"."Latitude",
    "Areas"."Altitude",
    "Areas"."PlanetId",
    ("Areas"."Type")::text AS "Type"
   FROM ONLY public."Areas"
UNION ALL
 SELECT ("Estates"."Id" + 300000) AS "Id",
    "Estates"."Name",
    "Estates"."Longitude",
    "Estates"."Latitude",
    "Estates"."Altitude",
    "Estates"."PlanetId",
    ("Estates"."Type")::text AS "Type"
   FROM ONLY public."Estates";


--
-- Name: Planets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Planets" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "X" integer,
    "Y" integer,
    "Width" integer,
    "Height" integer,
    "TechnicalName" text,
    "Description" text
);


--
-- Name: Maps_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Maps_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Maps_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Maps_Id_seq" OWNED BY public."Planets"."Id";


--
-- Name: Materials_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Materials_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Materials_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Materials_Id_seq" OWNED BY public."Materials"."Id";


--
-- Name: Materials_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Materials_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Type" text,
    "Weight" numeric,
    "Stackable" integer,
    "MaxStack" integer DEFAULT NULL,
    "Value" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Materials");


--
-- Name: MedicalChips_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."MedicalChips_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: MedicalChips_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."MedicalChips_Id_seq" OWNED BY public."MedicalChips"."Id";


--
-- Name: MedicalChips_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MedicalChips_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Level" integer,
    "Range" real,
    "Weight" numeric,
    "Heal" numeric,
    "StartInterval" numeric,
    "Uses" integer,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Decay" numeric,
    "AmmoBurn" integer,
    "Concentration" numeric,
    "Cooldown" numeric,
    "CooldownGroup" integer,
    "AmmoId" integer,
    "MinLvl" numeric,
    "MaxLvl" numeric,
    "SIB" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MedicalChips");


--
-- Name: MedicalTools_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."MedicalTools_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: MedicalTools_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."MedicalTools_Id_seq" OWNED BY public."MedicalTools"."Id";


--
-- Name: MedicalTools_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MedicalTools_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Weight" numeric,
    "Heal" numeric,
    "StartInterval" numeric,
    "Uses" integer,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Decay" numeric,
    "MinLvl" numeric,
    "MaxLvl" numeric,
    "SIB" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MedicalTools");


--
-- Name: MindforceImplants_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."MindforceImplants_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: MindforceImplants_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."MindforceImplants_Id_seq" OWNED BY public."MindforceImplants"."Id";


--
-- Name: MindforceImplants_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MindforceImplants_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text NOT NULL,
    "Weight" numeric,
    "MaxLvl" integer,
    "Absorption" double precision,
    "MinTT" numeric,
    "MaxTT" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MindforceImplants");


--
-- Name: MiscTools_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."MiscTools_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: MiscTools_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."MiscTools_Id_seq" OWNED BY public."MiscTools"."Id";


--
-- Name: MiscTools_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MiscTools_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Type" text,
    "Weight" numeric,
    "Decay" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "ProfessionId" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MiscTools");


--
-- Name: MissionChains; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MissionChains" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Description" text
);


--
-- Name: MissionChains_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."MissionChains_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: MissionChains_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."MissionChains_Id_seq" OWNED BY public."MissionChains"."Id";


--
-- Name: MissionChains_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MissionChains_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Description" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MissionChains");


--
-- Name: MissionObjectives; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MissionObjectives" (
    "Id" integer NOT NULL,
    "Step" integer NOT NULL,
    "Description" text,
    "Type" public."MissionObjectiveType",
    "Data" jsonb
);


--
-- Name: MissionObjectives_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."MissionObjectives_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: MissionObjectives_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."MissionObjectives_Id_seq" OWNED BY public."MissionObjectives"."Id";


--
-- Name: MissionObjectives_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MissionObjectives_audit" (
    "Id" integer DEFAULT NULL,
    "Step" integer,
    "Description" text,
    "Type" public."MissionObjectiveType",
    "Data" jsonb,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MissionObjectives");


--
-- Name: MissionPrerequisites; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MissionPrerequisites" (
    "MissionId" integer NOT NULL,
    "PrerequisiteId" integer NOT NULL
);


--
-- Name: MissionPrerequisites_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MissionPrerequisites_audit" (
    "MissionId" integer,
    "PrerequisiteId" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MissionPrerequisites");


--
-- Name: MissionRewards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MissionRewards" (
    "MissionId" integer NOT NULL,
    "ChoiceGroup" integer NOT NULL,
    "Type" public."MissionRewardType",
    "RewardId" integer,
    "Value" text
);


--
-- Name: MissionRewards_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MissionRewards_audit" (
    "MissionId" integer,
    "ChoiceGroup" integer,
    "Type" public."MissionRewardType",
    "RewardId" integer,
    "Value" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MissionRewards");


--
-- Name: Missions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Missions" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Description" text,
    "Type" public."MissionType" NOT NULL,
    "IsRepeatable" boolean DEFAULT false,
    "Cooldown" integer,
    "ChainId" integer,
    "EventId" integer,
    "StartLocationId" integer,
    "EndLocationId" integer,
    "PlanetId" integer
);


--
-- Name: Missions_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Missions_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Missions_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Missions_Id_seq" OWNED BY public."Missions"."Id";


--
-- Name: Missions_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Missions_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Description" text,
    "Type" public."MissionType",
    "IsRepeatable" boolean DEFAULT NULL,
    "Cooldown" integer,
    "ChainId" integer,
    "EventId" integer,
    "StartLocationId" integer,
    "EndLocationId" integer,
    "PlanetId" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Missions");


--
-- Name: MobAttacks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MobAttacks" (
    "MaturityId" integer NOT NULL,
    "Impact" numeric,
    "Stab" numeric,
    "Cut" numeric,
    "Penetration" numeric,
    "Shrapnel" numeric,
    "Acid" numeric,
    "Burn" numeric,
    "Cold" numeric,
    "Electric" numeric,
    "Name" text NOT NULL,
    "IsAoE" boolean,
    "Damage" numeric
);


--
-- Name: MobAttacks_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MobAttacks_audit" (
    "MaturityId" integer,
    "Impact" numeric,
    "Stab" numeric,
    "Cut" numeric,
    "Penetration" numeric,
    "Shrapnel" numeric,
    "Acid" numeric,
    "Burn" numeric,
    "Cold" numeric,
    "Electric" numeric,
    "Name" text,
    "IsAoE" boolean,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MobAttacks");


--
-- Name: MobLoots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MobLoots" (
    "MobId" integer NOT NULL,
    "MaturityId" integer,
    "ItemId" integer NOT NULL,
    "Frequency" text,
    "LastVU" text,
    "IsEvent" integer,
    "IsDropping" integer
);


--
-- Name: MobLoots_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MobLoots_audit" (
    "MobId" integer,
    "MaturityId" integer,
    "ItemId" integer,
    "Frequency" text,
    "LastVU" text,
    "IsEvent" integer,
    "IsDropping" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MobLoots");


--
-- Name: MobMaturities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MobMaturities" (
    "Id" integer NOT NULL,
    "MobId" integer NOT NULL,
    "Name" text,
    "Health" integer,
    "RegenerationInterval" numeric,
    "RegenerationAmount" numeric,
    "AttackSpeed" numeric,
    "DamagePotential" text,
    "DangerLevel" integer,
    "TamingLevel" numeric,
    "Agility" numeric,
    "Intelligence" numeric,
    "Psyche" numeric,
    "Stamina" numeric,
    "Strength" numeric,
    "MissChance" numeric,
    "ResistanceStab" numeric,
    "ResistanceCut" numeric,
    "ResistanceImpact" numeric,
    "ResistancePenetration" numeric,
    "ResistanceShrapnel" numeric,
    "ResistanceBurn" numeric,
    "ResistanceCold" numeric,
    "ResistanceAcid" numeric,
    "ResistanceElectric" numeric,
    "Description" text
);


--
-- Name: MobMaturities_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."MobMaturities_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: MobMaturities_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."MobMaturities_Id_seq" OWNED BY public."MobMaturities"."Id";


--
-- Name: MobMaturities_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MobMaturities_audit" (
    "Id" integer DEFAULT NULL,
    "MobId" integer,
    "Name" text,
    "Health" integer,
    "RegenerationInterval" numeric,
    "RegenerationAmount" numeric,
    "AttackSpeed" numeric,
    "DamagePotential" text,
    "DangerLevel" integer,
    "TamingLevel" numeric,
    "Agility" numeric,
    "Intelligence" numeric,
    "Psyche" numeric,
    "Stamina" numeric,
    "Strength" numeric,
    "MissChance" numeric,
    "ResistanceStab" numeric,
    "ResistanceCut" numeric,
    "ResistanceImpact" numeric,
    "ResistancePenetration" numeric,
    "ResistanceShrapnel" numeric,
    "ResistanceBurn" numeric,
    "ResistanceCold" numeric,
    "ResistanceAcid" numeric,
    "ResistanceElectric" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MobMaturities");


--
-- Name: MobSpawnMaturities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MobSpawnMaturities" (
    "AreaId" integer NOT NULL,
    "MaturityId" integer NOT NULL,
    "IsRare" integer DEFAULT 0
);


--
-- Name: MobSpawnMaturities_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MobSpawnMaturities_audit" (
    "AreaId" integer,
    "MaturityId" integer,
    "IsRare" integer DEFAULT NULL,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MobSpawnMaturities");


--
-- Name: MobSpawns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MobSpawns" (
    "AreaId" integer NOT NULL,
    "Density" integer,
    "IsShared" integer,
    "IsEvent" integer,
    "Notes" text,
    "Name" text,
    "Description" text
);


--
-- Name: MobSpawns_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MobSpawns_audit" (
    "AreaId" integer,
    "Density" integer,
    "IsShared" integer,
    "IsEvent" integer,
    "Notes" text,
    "Name" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MobSpawns");


--
-- Name: MobSpecies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MobSpecies" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "CodexBaseCost" numeric,
    "IsCat4Codex" integer,
    "Description" text,
    "CodexType" public."CodexType"
);


--
-- Name: MobSpecies_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."MobSpecies_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: MobSpecies_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."MobSpecies_Id_seq" OWNED BY public."MobSpecies"."Id";


--
-- Name: MobSpecies_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."MobSpecies_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "CodexBaseCost" numeric,
    "IsCat4Codex" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."MobSpecies");


--
-- Name: Mobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Mobs" (
    "Id" integer NOT NULL,
    "SpeciesId" integer,
    "Name" text NOT NULL,
    "PlanetId" integer,
    "Combat" text,
    "Attacks" integer,
    "Range" numeric,
    "Aggression" text,
    "Sweatable" integer,
    "DefensiveProfessionId" integer,
    "ScanningProfessionId" integer,
    "AggressionRange" numeric,
    "AttackRange" numeric,
    "Description" text,
    "Type" public."MobType"
);


--
-- Name: Mobs_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Mobs_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Mobs_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Mobs_Id_seq" OWNED BY public."Mobs"."Id";


--
-- Name: Mobs_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Mobs_audit" (
    "Id" integer DEFAULT NULL,
    "SpeciesId" integer,
    "Name" text,
    "PlanetId" integer,
    "Combat" text,
    "Attacks" integer,
    "Range" numeric,
    "Aggression" text,
    "Sweatable" integer,
    "DefensiveProfessionId" integer,
    "ScanningProfessionId" integer,
    "AggressionRange" numeric,
    "AttackRange" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Mobs");


--
-- Name: Npcs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Npcs" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Longitude" integer,
    "Latitude" integer,
    "Altitude" integer,
    "PlanetId" integer,
    "Description" text
);


--
-- Name: Npcs_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Npcs_Id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 2147483647
    CACHE 1;


--
-- Name: Npcs_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Npcs_Id_seq" OWNED BY public."Npcs"."Id";


--
-- Name: Npcs_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Npcs_audit" (
    "Id" integer DEFAULT nextval('public."Npcs_Id_seq"'::regclass),
    "Name" text,
    "Longitude" integer,
    "Latitude" integer,
    "Altitude" integer,
    "PlanetId" integer,
    "Description" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Npcs");


--
-- Name: PetEffects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."PetEffects" (
    "PetId" integer NOT NULL,
    "EffectId" integer NOT NULL,
    "Strength" integer NOT NULL,
    "Consumption" integer,
    "UnlockLevel" integer,
    "UnlockPED" integer,
    "UnlockEssence" integer,
    "UnlockRareEssence" integer,
    "UnlockCriteria" text,
    "UnlockCriteriaValue" integer
);


--
-- Name: PetEffects_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."PetEffects_audit" (
    "PetId" integer,
    "EffectId" integer,
    "Strength" integer,
    "Consumption" integer,
    "UnlockLevel" integer,
    "UnlockPED" integer,
    "UnlockEssence" integer,
    "UnlockRareEssence" integer,
    "UnlockCriteria" text,
    "UnlockCriteriaValue" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."PetEffects");


--
-- Name: Pets_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Pets_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Pets_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Pets_Id_seq" OWNED BY public."Pets"."Id";


--
-- Name: Pets_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Pets_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Rarity" text,
    "Training" text,
    "NutrioCapacity" integer,
    "NutrioConsumption" integer,
    "Exportable" integer,
    "PlanetId" integer,
    "TamingLevel" numeric,
    "Description" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Pets");


--
-- Name: Planets_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Planets_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "X" integer,
    "Y" integer,
    "Width" integer,
    "Height" integer,
    "TechnicalName" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Planets");


--
-- Name: ProfessionCategories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."ProfessionCategories" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL
);


--
-- Name: ProfessionCategories_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."ProfessionCategories_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ProfessionCategories_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."ProfessionCategories_Id_seq" OWNED BY public."ProfessionCategories"."Id";


--
-- Name: ProfessionCategories_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."ProfessionCategories_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."ProfessionCategories");


--
-- Name: ProfessionSkills; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."ProfessionSkills" (
    "ProfessionId" integer NOT NULL,
    "SkillId" integer NOT NULL,
    "Weight" integer
);


--
-- Name: ProfessionSkills_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."ProfessionSkills_audit" (
    "ProfessionId" integer,
    "SkillId" integer,
    "Weight" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."ProfessionSkills");


--
-- Name: Professions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Professions" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "CategoryId" integer,
    "Description" text
);


--
-- Name: Professions_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Professions_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Professions_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Professions_Id_seq" OWNED BY public."Professions"."Id";


--
-- Name: Professions_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Professions_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "CategoryId" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Professions");


--
-- Name: Refiners_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Refiners_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Refiners_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Refiners_Id_seq" OWNED BY public."Refiners"."Id";


--
-- Name: Refiners_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Refiners_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Weight" integer,
    "Uses" text,
    "Decay" real,
    "MaxTT" real,
    "MinTT" real,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Refiners");


--
-- Name: RefiningIngredients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."RefiningIngredients" (
    "RecipeId" integer NOT NULL,
    "ItemId" integer NOT NULL,
    "Amount" integer
);


--
-- Name: RefiningIngredients_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."RefiningIngredients_audit" (
    "RecipeId" integer,
    "ItemId" integer,
    "Amount" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."RefiningIngredients");


--
-- Name: RefiningRecipes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."RefiningRecipes" (
    "Id" integer NOT NULL,
    "ProductId" integer NOT NULL,
    "Amount" numeric
);


--
-- Name: RefiningRecipes_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."RefiningRecipes_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: RefiningRecipes_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."RefiningRecipes_Id_seq" OWNED BY public."RefiningRecipes"."Id";


--
-- Name: RefiningRecipes_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."RefiningRecipes_audit" (
    "Id" integer DEFAULT NULL,
    "ProductId" integer,
    "Amount" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."RefiningRecipes");


--
-- Name: Scanners_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Scanners_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Scanners_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Scanners_Id_seq" OWNED BY public."Scanners"."Id";


--
-- Name: Scanners_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Scanners_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Weight" integer,
    "Range" integer,
    "Uses" integer,
    "Decay" text,
    "MaxTT" integer,
    "MinTT" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Scanners");


--
-- Name: Sets; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public."Sets" AS
 SELECT ("ArmorSets"."Id" + 0) AS "Id",
    "ArmorSets"."Name",
    'ArmorSet'::text AS "Type"
   FROM ONLY public."ArmorSets"
UNION ALL
 SELECT ("EquipSets"."Id" + 100000) AS "Id",
    "EquipSets"."Name",
    'EquipSet'::text AS "Type"
   FROM ONLY public."EquipSets";


--
-- Name: Shops; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Shops" (
    "OwnerId" bigint,
    "EstateId" integer NOT NULL
);


--
-- Name: Shops_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Shops_audit" (
    "OwnerId" bigint,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL,
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "PlanetId" integer,
    "Longitude" integer,
    "Latitude" integer,
    "Altitude" integer,
    "Description" text
)
INHERITS (public."Shops");


--
-- Name: Signs_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Signs_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Signs_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Signs_Id_seq" OWNED BY public."Signs"."Id";


--
-- Name: Signs_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Signs_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Weight" numeric,
    "ItemPoints" integer,
    "AspectRatio" text,
    "LocalContentScreen" integer,
    "ImagesAndText" integer,
    "Effects" integer,
    "Multimedia" integer,
    "ParticipantContent" integer,
    "Cost" numeric,
    "MaxTT" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Signs");


--
-- Name: SkillCategories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."SkillCategories" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL
);


--
-- Name: SkillCategories_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."SkillCategories_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: SkillCategories_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."SkillCategories_Id_seq" OWNED BY public."SkillCategories"."Id";


--
-- Name: SkillCategories_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."SkillCategories_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."SkillCategories");


--
-- Name: SkillUnlocks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."SkillUnlocks" (
    "SkillId" integer NOT NULL,
    "ProfessionId" integer NOT NULL,
    "Level" integer NOT NULL
);


--
-- Name: SkillUnlocks_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."SkillUnlocks_audit" (
    "SkillId" integer,
    "ProfessionId" integer,
    "Level" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."SkillUnlocks");


--
-- Name: Skills; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Skills" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "CategoryId" integer NOT NULL,
    "HPIncrease" numeric,
    "Hidden" integer,
    "Description" text,
    "IsExtractable" boolean DEFAULT true
);


--
-- Name: Skills_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Skills_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Skills_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Skills_Id_seq" OWNED BY public."Skills"."Id";


--
-- Name: Skills_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Skills_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "CategoryId" integer,
    "HPIncrease" numeric,
    "Hidden" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Skills");


--
-- Name: StorageContainers_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."StorageContainers_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: StorageContainers_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."StorageContainers_Id_seq" OWNED BY public."StorageContainers"."Id";


--
-- Name: StorageContainers_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."StorageContainers_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Weight" numeric,
    "Capacity" integer,
    "MaxWeight" numeric,
    "MaxTT" numeric,
    "PlanetId" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."StorageContainers");


--
-- Name: StrongboxLoots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."StrongboxLoots" (
    "StrongboxId" integer NOT NULL,
    "ItemId" integer NOT NULL,
    "Rarity" public."StrongboxLootRarity" NOT NULL,
    "AvailableFrom" date,
    "AvailableUntil" date
);


--
-- Name: StrongboxLoots_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."StrongboxLoots_audit" (
    "StrongboxId" integer,
    "ItemId" integer,
    "Rarity" public."StrongboxLootRarity",
    "AvailableFrom" date,
    "AvailableUntil" date,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."StrongboxLoots");


--
-- Name: Strongboxes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Strongboxes" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Description" text
);


--
-- Name: Strongboxes_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Strongboxes_Id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 2147483647
    CACHE 1;


--
-- Name: Strongboxes_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Strongboxes_Id_seq" OWNED BY public."Strongboxes"."Id";


--
-- Name: Strongboxes_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Strongboxes_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Description" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Strongboxes");


--
-- Name: Tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Tags" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL
);


--
-- Name: Tags_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Tags_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Tags_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Tags_Id_seq" OWNED BY public."Tags"."Id";


--
-- Name: TeleportationChips_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."TeleportationChips_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: TeleportationChips_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."TeleportationChips_Id_seq" OWNED BY public."TeleportationChips"."Id";


--
-- Name: TeleportationChips_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."TeleportationChips_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Level" integer,
    "Weight" numeric,
    "Concentration" numeric,
    "Cooldown" numeric,
    "CooldownGroup" integer,
    "Range" numeric,
    "UsesPerMinute" integer,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Decay" numeric,
    "AmmoId" integer,
    "AmmoBurn" integer,
    "ProfessionId" integer,
    "MinLevel" numeric,
    "MaxLevel" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."TeleportationChips");


--
-- Name: Teleporters_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Teleporters_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Teleporters_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Teleporters_Id_seq" OWNED BY public."Teleporters"."Id";


--
-- Name: Teleporters_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Teleporters_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "PlanetId" integer,
    "Longitude" integer,
    "Latitude" integer,
    "Altitude" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Teleporters");


--
-- Name: TierMaterials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."TierMaterials" (
    "TierId" integer NOT NULL,
    "MaterialId" integer NOT NULL,
    "Amount" integer
);


--
-- Name: TierMaterials_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."TierMaterials_audit" (
    "TierId" integer,
    "MaterialId" integer,
    "Amount" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."TierMaterials");


--
-- Name: Tiers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Tiers" (
    "Id" integer NOT NULL,
    "ItemId" integer NOT NULL,
    "Tier" integer NOT NULL,
    "IsArmorSet" integer DEFAULT 0 NOT NULL
);


--
-- Name: Tiers_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Tiers_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Tiers_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Tiers_Id_seq" OWNED BY public."Tiers"."Id";


--
-- Name: Tiers_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Tiers_audit" (
    "Id" integer DEFAULT NULL,
    "ItemId" integer,
    "Tier" integer,
    "IsArmorSet" integer DEFAULT NULL,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Tiers");


--
-- Name: VehicleAttachmentSlots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."VehicleAttachmentSlots" (
    "VehicleId" integer NOT NULL,
    "AttachmentId" integer NOT NULL
);


--
-- Name: VehicleAttachmentSlots_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."VehicleAttachmentSlots_audit" (
    "VehicleId" integer,
    "AttachmentId" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."VehicleAttachmentSlots");


--
-- Name: VehicleAttachmentTypes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."VehicleAttachmentTypes" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "Description" text
);


--
-- Name: VehicleAttachmentType_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."VehicleAttachmentType_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: VehicleAttachmentType_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."VehicleAttachmentType_Id_seq" OWNED BY public."VehicleAttachmentTypes"."Id";


--
-- Name: VehicleAttachmentTypes_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."VehicleAttachmentTypes_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Description" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."VehicleAttachmentTypes");


--
-- Name: Vehicles_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Vehicles_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Vehicles_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Vehicles_Id_seq" OWNED BY public."Vehicles"."Id";


--
-- Name: Vehicles_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Vehicles_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Passengers" integer,
    "Weight" numeric,
    "SpawnedWeight" numeric,
    "CustomColors" integer,
    "CustomTextures" integer,
    "StorageCount" integer,
    "StorageWeight" numeric,
    "FuelMaterialId" integer,
    "FuelActive" numeric,
    "FuelPassive" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "WheelGrip" numeric,
    "EnginePower" numeric,
    "MaxSpeed" numeric,
    "MaxSI" numeric,
    "Stab" numeric,
    "Cut" numeric,
    "Impact" numeric,
    "Penetration" numeric,
    "Shrapnel" numeric,
    "Burn" numeric,
    "Cold" numeric,
    "Acid" numeric,
    "Electric" numeric,
    "Durability" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Vehicles");


--
-- Name: VendorOfferPrices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."VendorOfferPrices" (
    "OfferId" integer NOT NULL,
    "ItemId" integer NOT NULL,
    "Amount" integer
);


--
-- Name: VendorOfferPrices_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."VendorOfferPrices_audit" (
    "OfferId" integer,
    "ItemId" integer,
    "Amount" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."VendorOfferPrices");


--
-- Name: VendorOffers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."VendorOffers" (
    "Id" integer NOT NULL,
    "ItemId" integer NOT NULL,
    "VendorId" integer NOT NULL,
    "IsLimited" boolean DEFAULT false,
    "Value" numeric
);


--
-- Name: VendorOffers_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."VendorOffers_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: VendorOffers_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."VendorOffers_Id_seq" OWNED BY public."VendorOffers"."Id";


--
-- Name: VendorOffers_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."VendorOffers_audit" (
    "Id" integer DEFAULT NULL,
    "ItemId" integer,
    "VendorId" integer,
    "IsLimited" boolean DEFAULT NULL,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."VendorOffers");


--
-- Name: Vendors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Vendors" (
    "Id" integer NOT NULL,
    "Name" text NOT NULL,
    "PlanetId" integer,
    "Longitude" integer,
    "Latitude" integer,
    "Altitude" integer,
    "Description" text
);


--
-- Name: Vendors_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Vendors_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Vendors_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Vendors_Id_seq" OWNED BY public."Vendors"."Id";


--
-- Name: Vendors_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Vendors_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "PlanetId" integer,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Vendors");


--
-- Name: WeaponAmplifiers_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."WeaponAmplifiers_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: WeaponAmplifiers_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."WeaponAmplifiers_Id_seq" OWNED BY public."WeaponAmplifiers"."Id";


--
-- Name: WeaponAmplifiers_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."WeaponAmplifiers_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Type" text,
    "Weight" numeric,
    "Decay" numeric,
    "Ammo" integer,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Efficiency" numeric,
    "Stab" numeric,
    "Cut" numeric,
    "Impact" numeric,
    "Penetration" numeric,
    "Shrapnel" numeric,
    "Burn" numeric,
    "Cold" numeric,
    "Acid" numeric,
    "Electric" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."WeaponAmplifiers");


--
-- Name: WeaponVisionAttachments_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."WeaponVisionAttachments_Id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 2147483647
    CACHE 1;


--
-- Name: WeaponVisionAttachments_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."WeaponVisionAttachments_Id_seq" OWNED BY public."WeaponVisionAttachments"."Id";


--
-- Name: WeaponVisionAttachments_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."WeaponVisionAttachments_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Type" text,
    "Weight" numeric,
    "SkillMod" numeric,
    "SkillBonus" numeric,
    "Zoom" numeric,
    "Decay" numeric,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Efficiency" numeric,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."WeaponVisionAttachments");


--
-- Name: Weapons_Id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Weapons_Id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Weapons_Id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Weapons_Id_seq" OWNED BY public."Weapons"."Id";


--
-- Name: Weapons_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Weapons_audit" (
    "Id" integer DEFAULT NULL,
    "Name" text,
    "Class" text,
    "Type" text,
    "MFLevel" integer,
    "Range" numeric,
    "Weight" numeric,
    "ImpactRadius" numeric,
    "Attacks" numeric,
    "Decay" numeric,
    "AmmoBurn" integer,
    "MaxTT" numeric,
    "MinTT" numeric,
    "Efficiency" numeric,
    "Stab" numeric,
    "Cut" numeric,
    "Impact" numeric,
    "Penetration" numeric,
    "Shrapnel" numeric,
    "Burn" numeric,
    "Cold" numeric,
    "Acid" numeric,
    "Electric" numeric,
    "SIB" integer,
    "Concentration" numeric,
    "Cooldown" numeric,
    "CooldownGroup" text,
    "MinHit" numeric,
    "MaxHit" numeric,
    "MinDmg" numeric,
    "MaxDmg" numeric,
    "PlanetId" integer,
    "AttachmentTypeId" integer,
    "AmmoId" integer,
    "ProfessionHitId" integer,
    "ProfessionDmgId" integer,
    "Category" text,
    operation character(1) NOT NULL,
    stamp timestamp without time zone NOT NULL,
    userid text NOT NULL
)
INHERITS (public."Weapons");


--
-- Name: Absorbers Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Absorbers" ALTER COLUMN "Id" SET DEFAULT nextval('public."Absorbers_Id_seq"'::regclass);


--
-- Name: Areas Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Areas" ALTER COLUMN "Id" SET DEFAULT nextval('public."Areas_Id_seq"'::regclass);


--
-- Name: ArmorPlatings Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."ArmorPlatings" ALTER COLUMN "Id" SET DEFAULT nextval('public."ArmorPlatings_Id_seq"'::regclass);


--
-- Name: ArmorSets Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."ArmorSets" ALTER COLUMN "Id" SET DEFAULT nextval('public."ArmorSets_Id_seq"'::regclass);


--
-- Name: Armors Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Armors" ALTER COLUMN "Id" SET DEFAULT nextval('public."Armors_Id_seq"'::regclass);


--
-- Name: BlueprintBooks Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."BlueprintBooks" ALTER COLUMN "Id" SET DEFAULT nextval('public."BlueprintBooks_Id_seq"'::regclass);


--
-- Name: BlueprintTypes Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."BlueprintTypes" ALTER COLUMN "Id" SET DEFAULT nextval('public."BlueprintTypes_Id_seq"'::regclass);


--
-- Name: Blueprints Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Blueprints" ALTER COLUMN "Id" SET DEFAULT nextval('public."Blueprints_Id_seq"'::regclass);


--
-- Name: Clothes Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Clothes" ALTER COLUMN "Id" SET DEFAULT nextval('public."Clothes_Id_seq"'::regclass);


--
-- Name: Consumables Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Consumables" ALTER COLUMN "Id" SET DEFAULT nextval('public."Consumables_Id_seq"'::regclass);


--
-- Name: CreatureControlCapsules Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."CreatureControlCapsules" ALTER COLUMN "Id" SET DEFAULT nextval('public."CreatureControlCapsules_Id_seq"'::regclass);


--
-- Name: Decorations Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Decorations" ALTER COLUMN "Id" SET DEFAULT nextval('public."Decorations_Id_seq"'::regclass);


--
-- Name: EffectChips Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EffectChips" ALTER COLUMN "Id" SET DEFAULT nextval('public."EffectChips_Id_seq"'::regclass);


--
-- Name: Effects Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Effects" ALTER COLUMN "Id" SET DEFAULT nextval('public."Effects_Id_seq"'::regclass);


--
-- Name: EnhancerType Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EnhancerType" ALTER COLUMN "Id" SET DEFAULT nextval('public."EnhancerType_Id_seq"'::regclass);


--
-- Name: EquipSets Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EquipSets" ALTER COLUMN "Id" SET DEFAULT nextval('public."EquipSets_Id_seq"'::regclass);


--
-- Name: EstateSections EstateId; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EstateSections" ALTER COLUMN "EstateId" SET DEFAULT nextval('public."EstateSections_EstateId_seq"'::regclass);


--
-- Name: Estates Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Estates" ALTER COLUMN "Id" SET DEFAULT nextval('public."Estates_Id_seq"'::regclass);


--
-- Name: Excavators Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Excavators" ALTER COLUMN "Id" SET DEFAULT nextval('public."Excavators_Id_seq"'::regclass);


--
-- Name: FinderAmplifiers Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."FinderAmplifiers" ALTER COLUMN "Id" SET DEFAULT nextval('public."FinderAmplifiers_Id_seq"'::regclass);


--
-- Name: Finders Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Finders" ALTER COLUMN "Id" SET DEFAULT nextval('public."Finders_Id_seq"'::regclass);


--
-- Name: Furniture Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Furniture" ALTER COLUMN "Id" SET DEFAULT nextval('public."Furniture_Id_seq"'::regclass);


--
-- Name: Materials Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Materials" ALTER COLUMN "Id" SET DEFAULT nextval('public."Materials_Id_seq"'::regclass);


--
-- Name: MedicalChips Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MedicalChips" ALTER COLUMN "Id" SET DEFAULT nextval('public."MedicalChips_Id_seq"'::regclass);


--
-- Name: MedicalTools Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MedicalTools" ALTER COLUMN "Id" SET DEFAULT nextval('public."MedicalTools_Id_seq"'::regclass);


--
-- Name: MindforceImplants Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MindforceImplants" ALTER COLUMN "Id" SET DEFAULT nextval('public."MindforceImplants_Id_seq"'::regclass);


--
-- Name: MiscTools Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MiscTools" ALTER COLUMN "Id" SET DEFAULT nextval('public."MiscTools_Id_seq"'::regclass);


--
-- Name: MissionChains Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MissionChains" ALTER COLUMN "Id" SET DEFAULT nextval('public."MissionChains_Id_seq"'::regclass);


--
-- Name: MissionObjectives Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MissionObjectives" ALTER COLUMN "Id" SET DEFAULT nextval('public."MissionObjectives_Id_seq"'::regclass);


--
-- Name: Missions Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Missions" ALTER COLUMN "Id" SET DEFAULT nextval('public."Missions_Id_seq"'::regclass);


--
-- Name: MobMaturities Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobMaturities" ALTER COLUMN "Id" SET DEFAULT nextval('public."MobMaturities_Id_seq"'::regclass);


--
-- Name: MobSpecies Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobSpecies" ALTER COLUMN "Id" SET DEFAULT nextval('public."MobSpecies_Id_seq"'::regclass);


--
-- Name: Mobs Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Mobs" ALTER COLUMN "Id" SET DEFAULT nextval('public."Mobs_Id_seq"'::regclass);


--
-- Name: Npcs Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Npcs" ALTER COLUMN "Id" SET DEFAULT nextval('public."Npcs_Id_seq"'::regclass);


--
-- Name: Pets Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Pets" ALTER COLUMN "Id" SET DEFAULT nextval('public."Pets_Id_seq"'::regclass);


--
-- Name: Planets Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Planets" ALTER COLUMN "Id" SET DEFAULT nextval('public."Maps_Id_seq"'::regclass);


--
-- Name: ProfessionCategories Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."ProfessionCategories" ALTER COLUMN "Id" SET DEFAULT nextval('public."ProfessionCategories_Id_seq"'::regclass);


--
-- Name: Professions Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Professions" ALTER COLUMN "Id" SET DEFAULT nextval('public."Professions_Id_seq"'::regclass);


--
-- Name: Refiners Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Refiners" ALTER COLUMN "Id" SET DEFAULT nextval('public."Refiners_Id_seq"'::regclass);


--
-- Name: RefiningRecipes Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."RefiningRecipes" ALTER COLUMN "Id" SET DEFAULT nextval('public."RefiningRecipes_Id_seq"'::regclass);


--
-- Name: Scanners Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Scanners" ALTER COLUMN "Id" SET DEFAULT nextval('public."Scanners_Id_seq"'::regclass);


--
-- Name: Signs Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Signs" ALTER COLUMN "Id" SET DEFAULT nextval('public."Signs_Id_seq"'::regclass);


--
-- Name: SkillCategories Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."SkillCategories" ALTER COLUMN "Id" SET DEFAULT nextval('public."SkillCategories_Id_seq"'::regclass);


--
-- Name: Skills Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Skills" ALTER COLUMN "Id" SET DEFAULT nextval('public."Skills_Id_seq"'::regclass);


--
-- Name: Skills_audit IsExtractable; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Skills_audit" ALTER COLUMN "IsExtractable" SET DEFAULT true;


--
-- Name: StorageContainers Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."StorageContainers" ALTER COLUMN "Id" SET DEFAULT nextval('public."StorageContainers_Id_seq"'::regclass);


--
-- Name: Strongboxes Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Strongboxes" ALTER COLUMN "Id" SET DEFAULT nextval('public."Strongboxes_Id_seq"'::regclass);


--
-- Name: Tags Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Tags" ALTER COLUMN "Id" SET DEFAULT nextval('public."Tags_Id_seq"'::regclass);


--
-- Name: TeleportationChips Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."TeleportationChips" ALTER COLUMN "Id" SET DEFAULT nextval('public."TeleportationChips_Id_seq"'::regclass);


--
-- Name: Teleporters Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Teleporters" ALTER COLUMN "Id" SET DEFAULT nextval('public."Teleporters_Id_seq"'::regclass);


--
-- Name: Tiers Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Tiers" ALTER COLUMN "Id" SET DEFAULT nextval('public."Tiers_Id_seq"'::regclass);


--
-- Name: VehicleAttachmentTypes Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VehicleAttachmentTypes" ALTER COLUMN "Id" SET DEFAULT nextval('public."VehicleAttachmentType_Id_seq"'::regclass);


--
-- Name: Vehicles Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Vehicles" ALTER COLUMN "Id" SET DEFAULT nextval('public."Vehicles_Id_seq"'::regclass);


--
-- Name: VendorOffers Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VendorOffers" ALTER COLUMN "Id" SET DEFAULT nextval('public."VendorOffers_Id_seq"'::regclass);


--
-- Name: Vendors Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Vendors" ALTER COLUMN "Id" SET DEFAULT nextval('public."Vendors_Id_seq"'::regclass);


--
-- Name: WeaponAmplifiers Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."WeaponAmplifiers" ALTER COLUMN "Id" SET DEFAULT nextval('public."WeaponAmplifiers_Id_seq"'::regclass);


--
-- Name: WeaponVisionAttachments Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."WeaponVisionAttachments" ALTER COLUMN "Id" SET DEFAULT nextval('public."WeaponVisionAttachments_Id_seq"'::regclass);


--
-- Name: Weapons Id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Weapons" ALTER COLUMN "Id" SET DEFAULT nextval('public."Weapons_Id_seq"'::regclass);


--
-- Name: Absorbers Absorbers_Name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Absorbers"
    ADD CONSTRAINT "Absorbers_Name_key" UNIQUE ("Name");


--
-- Name: Absorbers Absorbers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Absorbers"
    ADD CONSTRAINT "Absorbers_pkey" PRIMARY KEY ("Id");


--
-- Name: Areas Areas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Areas"
    ADD CONSTRAINT "Areas_pkey" PRIMARY KEY ("Id");


--
-- Name: ArmorPlatings ArmorPlatings_Name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."ArmorPlatings"
    ADD CONSTRAINT "ArmorPlatings_Name_key" UNIQUE ("Name");


--
-- Name: ArmorPlatings ArmorPlatings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."ArmorPlatings"
    ADD CONSTRAINT "ArmorPlatings_pkey" PRIMARY KEY ("Id");


--
-- Name: ArmorSets ArmorSets_Name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."ArmorSets"
    ADD CONSTRAINT "ArmorSets_Name_key" UNIQUE ("Name");


--
-- Name: ArmorSets ArmorSets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."ArmorSets"
    ADD CONSTRAINT "ArmorSets_pkey" PRIMARY KEY ("Id");


--
-- Name: Armors Armors_Name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Armors"
    ADD CONSTRAINT "Armors_Name_key" UNIQUE ("Name");


--
-- Name: Armors Armors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Armors"
    ADD CONSTRAINT "Armors_pkey" PRIMARY KEY ("Id");


--
-- Name: BlueprintBooks BlueprintBooks_Name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."BlueprintBooks"
    ADD CONSTRAINT "BlueprintBooks_Name_key" UNIQUE ("Name");


--
-- Name: BlueprintBooks BlueprintBooks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."BlueprintBooks"
    ADD CONSTRAINT "BlueprintBooks_pkey" PRIMARY KEY ("Id");


--
-- Name: BlueprintDrops BlueprintDrops_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."BlueprintDrops"
    ADD CONSTRAINT "BlueprintDrops_pkey" PRIMARY KEY ("SourceId", "DropId");


--
-- Name: BlueprintMaterials BlueprintMaterials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."BlueprintMaterials"
    ADD CONSTRAINT "BlueprintMaterials_pkey" PRIMARY KEY ("BlueprintId", "ItemId");


--
-- Name: BlueprintTypes BlueprintTypes_Name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."BlueprintTypes"
    ADD CONSTRAINT "BlueprintTypes_Name_key" UNIQUE ("Name");


--
-- Name: BlueprintTypes BlueprintTypes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."BlueprintTypes"
    ADD CONSTRAINT "BlueprintTypes_pkey" PRIMARY KEY ("Id");


--
-- Name: Blueprints Blueprints_Name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Blueprints"
    ADD CONSTRAINT "Blueprints_Name_key" UNIQUE ("Name");


--
-- Name: Blueprints Blueprints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Blueprints"
    ADD CONSTRAINT "Blueprints_pkey" PRIMARY KEY ("Id");


--
-- Name: Clothes Clothes_Name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Clothes"
    ADD CONSTRAINT "Clothes_Name_key" UNIQUE ("Name");


--
-- Name: Clothes Clothes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Clothes"
    ADD CONSTRAINT "Clothes_pkey" PRIMARY KEY ("Id");


--
-- Name: Consumables Consumables_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Consumables"
    ADD CONSTRAINT "Consumables_pkey" PRIMARY KEY ("Id");


--
-- Name: CreatureControlCapsules CreatureControlCapsules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."CreatureControlCapsules"
    ADD CONSTRAINT "CreatureControlCapsules_pkey" PRIMARY KEY ("Id");


--
-- Name: Decorations Decorations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Decorations"
    ADD CONSTRAINT "Decorations_pkey" PRIMARY KEY ("Id");


--
-- Name: EffectChips EffectChips_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EffectChips"
    ADD CONSTRAINT "EffectChips_pkey" PRIMARY KEY ("Id");


--
-- Name: EffectsOnConsume EffectsOnConsume_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EffectsOnConsume"
    ADD CONSTRAINT "EffectsOnConsume_pkey" PRIMARY KEY ("ConsumableId", "EffectId");


--
-- Name: EffectsOnEquip EffectsOnEquip_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EffectsOnEquip"
    ADD CONSTRAINT "EffectsOnEquip_pkey" PRIMARY KEY ("ItemId", "EffectId");


--
-- Name: EffectsOnSetEquip EffectsOnSetEquip_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EffectsOnSetEquip"
    ADD CONSTRAINT "EffectsOnSetEquip_pkey" PRIMARY KEY ("SetId", "EffectId", "MinSetPieces");


--
-- Name: EffectsOnUse EffectsOnUse_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EffectsOnUse"
    ADD CONSTRAINT "EffectsOnUse_pkey" PRIMARY KEY ("ItemId", "EffectId");


--
-- Name: Effects Effects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Effects"
    ADD CONSTRAINT "Effects_pkey" PRIMARY KEY ("Id");


--
-- Name: EnhancerType EnhancerType_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EnhancerType"
    ADD CONSTRAINT "EnhancerType_pkey" PRIMARY KEY ("Id");


--
-- Name: EquipSetItems EquipSetItems_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EquipSetItems"
    ADD CONSTRAINT "EquipSetItems_pkey" PRIMARY KEY ("EquipSetId", "ItemId");


--
-- Name: EquipSets EquipSets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EquipSets"
    ADD CONSTRAINT "EquipSets_pkey" PRIMARY KEY ("Id");


--
-- Name: EstateSections EstateSections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EstateSections"
    ADD CONSTRAINT "EstateSections_pkey" PRIMARY KEY ("EstateId", "Name");


--
-- Name: Estates Estates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Estates"
    ADD CONSTRAINT "Estates_pkey" PRIMARY KEY ("Id");


--
-- Name: Excavators Excavators_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Excavators"
    ADD CONSTRAINT "Excavators_pkey" PRIMARY KEY ("Id");


--
-- Name: FinderAmplifiers FinderAmplifiers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."FinderAmplifiers"
    ADD CONSTRAINT "FinderAmplifiers_pkey" PRIMARY KEY ("Id");


--
-- Name: Finders Finders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Finders"
    ADD CONSTRAINT "Finders_pkey" PRIMARY KEY ("Id");


--
-- Name: Furniture Furniture_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Furniture"
    ADD CONSTRAINT "Furniture_pkey" PRIMARY KEY ("Id");


--
-- Name: ItemTags ItemTags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."ItemTags"
    ADD CONSTRAINT "ItemTags_pkey" PRIMARY KEY ("ItemId", "TagId");


--
-- Name: Planets Maps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Planets"
    ADD CONSTRAINT "Maps_pkey" PRIMARY KEY ("Id");


--
-- Name: Materials Materials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Materials"
    ADD CONSTRAINT "Materials_pkey" PRIMARY KEY ("Id");


--
-- Name: MedicalChips MedicalChips_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MedicalChips"
    ADD CONSTRAINT "MedicalChips_pkey" PRIMARY KEY ("Id");


--
-- Name: MedicalTools MedicalTools_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MedicalTools"
    ADD CONSTRAINT "MedicalTools_pkey" PRIMARY KEY ("Id");


--
-- Name: MindforceImplants MindforceImplants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MindforceImplants"
    ADD CONSTRAINT "MindforceImplants_pkey" PRIMARY KEY ("Id");


--
-- Name: MiscTools MiscTools_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MiscTools"
    ADD CONSTRAINT "MiscTools_pkey" PRIMARY KEY ("Id");


--
-- Name: MissionChains MissionChains_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MissionChains"
    ADD CONSTRAINT "MissionChains_pkey" PRIMARY KEY ("Id");


--
-- Name: MissionObjectives MissionObjectives_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MissionObjectives"
    ADD CONSTRAINT "MissionObjectives_pkey" PRIMARY KEY ("Id", "Step");


--
-- Name: MissionPrerequisites MissionPrerequisites_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MissionPrerequisites"
    ADD CONSTRAINT "MissionPrerequisites_pkey" PRIMARY KEY ("MissionId", "PrerequisiteId");


--
-- Name: MissionRewards MissionRewards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MissionRewards"
    ADD CONSTRAINT "MissionRewards_pkey" PRIMARY KEY ("MissionId");


--
-- Name: Missions Missions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Missions"
    ADD CONSTRAINT "Missions_pkey" PRIMARY KEY ("Id");


--
-- Name: MobAttacks MobAttacks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobAttacks"
    ADD CONSTRAINT "MobAttacks_pkey" PRIMARY KEY ("Name", "MaturityId");


--
-- Name: MobLoots MobLoots_MobId_MaturityId_ItemId_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobLoots"
    ADD CONSTRAINT "MobLoots_MobId_MaturityId_ItemId_key" UNIQUE ("MobId", "MaturityId", "ItemId");


--
-- Name: MobLoots MobLoots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobLoots"
    ADD CONSTRAINT "MobLoots_pkey" PRIMARY KEY ("MobId", "ItemId");


--
-- Name: MobMaturities MobMaturities_MobId_Name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobMaturities"
    ADD CONSTRAINT "MobMaturities_MobId_Name_key" UNIQUE ("MobId", "Name");


--
-- Name: MobMaturities MobMaturities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobMaturities"
    ADD CONSTRAINT "MobMaturities_pkey" PRIMARY KEY ("Id");


--
-- Name: MobSpawnMaturities MobSpawnMaturities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobSpawnMaturities"
    ADD CONSTRAINT "MobSpawnMaturities_pkey" PRIMARY KEY ("AreaId", "MaturityId");


--
-- Name: MobSpawns MobSpawns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobSpawns"
    ADD CONSTRAINT "MobSpawns_pkey" PRIMARY KEY ("AreaId");


--
-- Name: MobSpecies MobSpecies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobSpecies"
    ADD CONSTRAINT "MobSpecies_pkey" PRIMARY KEY ("Id");


--
-- Name: Mobs Mobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Mobs"
    ADD CONSTRAINT "Mobs_pkey" PRIMARY KEY ("Id");


--
-- Name: Npcs Npcs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Npcs"
    ADD CONSTRAINT "Npcs_pkey" PRIMARY KEY ("Id");


--
-- Name: PetEffects PetEffects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."PetEffects"
    ADD CONSTRAINT "PetEffects_pkey" PRIMARY KEY ("PetId", "EffectId", "Strength");


--
-- Name: Pets Pets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Pets"
    ADD CONSTRAINT "Pets_pkey" PRIMARY KEY ("Id");


--
-- Name: ProfessionCategories ProfessionCategories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."ProfessionCategories"
    ADD CONSTRAINT "ProfessionCategories_pkey" PRIMARY KEY ("Id");


--
-- Name: ProfessionSkills ProfessionSkills_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."ProfessionSkills"
    ADD CONSTRAINT "ProfessionSkills_pkey" PRIMARY KEY ("ProfessionId", "SkillId");


--
-- Name: Professions Professions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Professions"
    ADD CONSTRAINT "Professions_pkey" PRIMARY KEY ("Id");


--
-- Name: Refiners Refiners_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Refiners"
    ADD CONSTRAINT "Refiners_pkey" PRIMARY KEY ("Id");


--
-- Name: RefiningIngredients RefiningIngredients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."RefiningIngredients"
    ADD CONSTRAINT "RefiningIngredients_pkey" PRIMARY KEY ("RecipeId", "ItemId");


--
-- Name: RefiningRecipes RefiningRecipes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."RefiningRecipes"
    ADD CONSTRAINT "RefiningRecipes_pkey" PRIMARY KEY ("Id");


--
-- Name: Scanners Scanners_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Scanners"
    ADD CONSTRAINT "Scanners_pkey" PRIMARY KEY ("Id");


--
-- Name: Signs Signs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Signs"
    ADD CONSTRAINT "Signs_pkey" PRIMARY KEY ("Id");


--
-- Name: SkillCategories SkillCategories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."SkillCategories"
    ADD CONSTRAINT "SkillCategories_pkey" PRIMARY KEY ("Id");


--
-- Name: SkillUnlocks SkillUnlocks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."SkillUnlocks"
    ADD CONSTRAINT "SkillUnlocks_pkey" PRIMARY KEY ("SkillId", "ProfessionId");


--
-- Name: Skills Skills_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Skills"
    ADD CONSTRAINT "Skills_pkey" PRIMARY KEY ("Id");


--
-- Name: StorageContainers StorageContainers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."StorageContainers"
    ADD CONSTRAINT "StorageContainers_pkey" PRIMARY KEY ("Id");


--
-- Name: StrongboxLoots StrongboxLoots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."StrongboxLoots"
    ADD CONSTRAINT "StrongboxLoots_pkey" PRIMARY KEY ("StrongboxId", "ItemId");


--
-- Name: Strongboxes Strongboxes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Strongboxes"
    ADD CONSTRAINT "Strongboxes_pkey" PRIMARY KEY ("Id");


--
-- Name: Tags Tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Tags"
    ADD CONSTRAINT "Tags_pkey" PRIMARY KEY ("Id");


--
-- Name: TeleportationChips TeleportationChips_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."TeleportationChips"
    ADD CONSTRAINT "TeleportationChips_pkey" PRIMARY KEY ("Id");


--
-- Name: Teleporters Teleporters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Teleporters"
    ADD CONSTRAINT "Teleporters_pkey" PRIMARY KEY ("Id");


--
-- Name: TierMaterials TierMaterials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."TierMaterials"
    ADD CONSTRAINT "TierMaterials_pkey" PRIMARY KEY ("TierId", "MaterialId");


--
-- Name: Tiers Tiers_ItemId_Tier_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Tiers"
    ADD CONSTRAINT "Tiers_ItemId_Tier_key" UNIQUE ("ItemId", "Tier");


--
-- Name: Tiers Tiers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Tiers"
    ADD CONSTRAINT "Tiers_pkey" PRIMARY KEY ("Id");


--
-- Name: VehicleAttachmentSlots VehicleAttachmentSlots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VehicleAttachmentSlots"
    ADD CONSTRAINT "VehicleAttachmentSlots_pkey" PRIMARY KEY ("VehicleId", "AttachmentId");


--
-- Name: VehicleAttachmentTypes VehicleAttachmentType_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VehicleAttachmentTypes"
    ADD CONSTRAINT "VehicleAttachmentType_pkey" PRIMARY KEY ("Id");


--
-- Name: Vehicles Vehicles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Vehicles"
    ADD CONSTRAINT "Vehicles_pkey" PRIMARY KEY ("Id");


--
-- Name: VendorOfferPrices VendorOfferPrices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VendorOfferPrices"
    ADD CONSTRAINT "VendorOfferPrices_pkey" PRIMARY KEY ("ItemId", "OfferId");


--
-- Name: VendorOffers VendorOffers_ItemId_VendorId_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VendorOffers"
    ADD CONSTRAINT "VendorOffers_ItemId_VendorId_key" UNIQUE ("ItemId", "VendorId");


--
-- Name: VendorOffers VendorOffers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VendorOffers"
    ADD CONSTRAINT "VendorOffers_pkey" PRIMARY KEY ("Id");


--
-- Name: Vendors Vendors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Vendors"
    ADD CONSTRAINT "Vendors_pkey" PRIMARY KEY ("Id");


--
-- Name: WeaponAmplifiers WeaponAmplifiers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."WeaponAmplifiers"
    ADD CONSTRAINT "WeaponAmplifiers_pkey" PRIMARY KEY ("Id");


--
-- Name: WeaponVisionAttachments WeaponVisionAttachments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."WeaponVisionAttachments"
    ADD CONSTRAINT "WeaponVisionAttachments_pkey" PRIMARY KEY ("Id");


--
-- Name: Weapons Weapons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Weapons"
    ADD CONSTRAINT "Weapons_pkey" PRIMARY KEY ("Id");


--
-- Name: Absorbers_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Absorbers_name_idx" ON public."Absorbers" USING btree ("Name");


--
-- Name: Areas_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Areas_name_idx" ON public."Areas" USING btree ("Name");


--
-- Name: ArmorPlatings_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "ArmorPlatings_name_idx" ON public."ArmorPlatings" USING btree ("Name");


--
-- Name: ArmorSets_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "ArmorSets_name_idx" ON public."ArmorSets" USING btree ("Name");


--
-- Name: Armors_SetId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Armors_SetId_idx" ON public."Armors" USING btree ("SetId") WITH (deduplicate_items='true');


--
-- Name: Armors_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Armors_name_idx" ON public."Armors" USING btree ("Name");


--
-- Name: BlueprintBooks_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "BlueprintBooks_name_idx" ON public."BlueprintBooks" USING btree ("Name");


--
-- Name: BlueprintTypes_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "BlueprintTypes_name_idx" ON public."BlueprintTypes" USING btree ("Name");


--
-- Name: Blueprints_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Blueprints_name_idx" ON public."Blueprints" USING btree ("Name");


--
-- Name: Clothes_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Clothes_name_idx" ON public."Clothes" USING btree ("Name");


--
-- Name: Consumables_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Consumables_name_idx" ON public."Consumables" USING btree ("Name");


--
-- Name: CreatureControlCapsules_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "CreatureControlCapsules_name_idx" ON public."CreatureControlCapsules" USING btree ("Name");


--
-- Name: Decorations_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Decorations_name_idx" ON public."Decorations" USING btree ("Name");


--
-- Name: EffectChips_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "EffectChips_name_idx" ON public."EffectChips" USING btree ("Name");


--
-- Name: Effects_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Effects_name_idx" ON public."Effects" USING btree ("Name");


--
-- Name: EnhancerType_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "EnhancerType_name_idx" ON public."EnhancerType" USING btree ("Name");


--
-- Name: EquipSets_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "EquipSets_name_idx" ON public."EquipSets" USING btree ("Name");


--
-- Name: Estates_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Estates_name_idx" ON public."Estates" USING btree ("Name");


--
-- Name: Excavators_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Excavators_name_idx" ON public."Excavators" USING btree ("Name");


--
-- Name: FinderAmplifiers_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "FinderAmplifiers_name_idx" ON public."FinderAmplifiers" USING btree ("Name");


--
-- Name: Finders_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Finders_name_idx" ON public."Finders" USING btree ("Name");


--
-- Name: Furniture_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Furniture_name_idx" ON public."Furniture" USING btree ("Name");


--
-- Name: Materials_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Materials_name_idx" ON public."Materials" USING btree ("Name");


--
-- Name: MedicalChips_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "MedicalChips_name_idx" ON public."MedicalChips" USING btree ("Name");


--
-- Name: MedicalTools_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "MedicalTools_name_idx" ON public."MedicalTools" USING btree ("Name");


--
-- Name: MindforceImplants_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "MindforceImplants_name_idx" ON public."MindforceImplants" USING btree ("Name");


--
-- Name: MiscTools_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "MiscTools_name_idx" ON public."MiscTools" USING btree ("Name");


--
-- Name: MobAttacks_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "MobAttacks_name_idx" ON public."MobAttacks" USING btree ("Name");


--
-- Name: MobMaturities_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "MobMaturities_name_idx" ON public."MobMaturities" USING btree ("Name");


--
-- Name: MobSpecies_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "MobSpecies_name_idx" ON public."MobSpecies" USING btree ("Name");


--
-- Name: Mobs_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Mobs_name_idx" ON public."Mobs" USING btree ("Name");


--
-- Name: Pets_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Pets_name_idx" ON public."Pets" USING btree ("Name");


--
-- Name: Planets_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Planets_name_idx" ON public."Planets" USING btree ("Name");


--
-- Name: ProfessionCategories_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "ProfessionCategories_name_idx" ON public."ProfessionCategories" USING btree ("Name");


--
-- Name: Professions_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Professions_name_idx" ON public."Professions" USING btree ("Name");


--
-- Name: Refiners_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Refiners_name_idx" ON public."Refiners" USING btree ("Name");


--
-- Name: Scanners_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Scanners_name_idx" ON public."Scanners" USING btree ("Name");


--
-- Name: Signs_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Signs_name_idx" ON public."Signs" USING btree ("Name");


--
-- Name: SkillCategories_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "SkillCategories_name_idx" ON public."SkillCategories" USING btree ("Name");


--
-- Name: Skills_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Skills_name_idx" ON public."Skills" USING btree ("Name");


--
-- Name: StorageContainers_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "StorageContainers_name_idx" ON public."StorageContainers" USING btree ("Name");


--
-- Name: TeleportationChips_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "TeleportationChips_name_idx" ON public."TeleportationChips" USING btree ("Name");


--
-- Name: Teleporters_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Teleporters_name_idx" ON public."Teleporters" USING btree ("Name");


--
-- Name: TierMaterials_TierId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "TierMaterials_TierId_idx" ON public."TierMaterials" USING btree ("TierId") WITH (deduplicate_items='true');


--
-- Name: VehicleAttachmentTypes_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "VehicleAttachmentTypes_name_idx" ON public."VehicleAttachmentTypes" USING btree ("Name");


--
-- Name: Vehicles_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Vehicles_name_idx" ON public."Vehicles" USING btree ("Name");


--
-- Name: Vendors_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Vendors_name_idx" ON public."Vendors" USING btree ("Name");


--
-- Name: WeaponAmplifiers_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "WeaponAmplifiers_name_idx" ON public."WeaponAmplifiers" USING btree ("Name");


--
-- Name: WeaponVisionAttachments_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "WeaponVisionAttachments_name_idx" ON public."WeaponVisionAttachments" USING btree ("Name");


--
-- Name: Weapons_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Weapons_name_idx" ON public."Weapons" USING btree ("Name");


--
-- Name: idx_areas_planetid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_areas_planetid ON public."Areas" USING btree ("PlanetId");


--
-- Name: idx_blueprintmaterials_blueprintid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_blueprintmaterials_blueprintid ON public."BlueprintMaterials" USING btree ("BlueprintId");


--
-- Name: idx_blueprintmaterials_itemid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_blueprintmaterials_itemid ON public."BlueprintMaterials" USING btree ("ItemId");


--
-- Name: idx_blueprintmaterials_itemid_blueprintid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_blueprintmaterials_itemid_blueprintid ON public."BlueprintMaterials" USING btree ("ItemId", "BlueprintId");


--
-- Name: idx_effectsonsetequip_effectid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_effectsonsetequip_effectid ON public."EffectsOnSetEquip" USING btree ("EffectId");


--
-- Name: idx_effectsonsetequip_setid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_effectsonsetequip_setid ON public."EffectsOnSetEquip" USING btree ("SetId");


--
-- Name: idx_effectsonsetequip_setid_effectid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_effectsonsetequip_setid_effectid ON public."EffectsOnSetEquip" USING btree ("SetId", "EffectId");


--
-- Name: idx_equipsetitems_itemid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_equipsetitems_itemid ON public."EquipSetItems" USING btree ("ItemId");


--
-- Name: idx_mob_attacks_maturity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mob_attacks_maturity_id ON public."MobAttacks" USING btree ("MaturityId");


--
-- Name: idx_mob_loots_mob_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mob_loots_mob_id ON public."MobLoots" USING btree ("MobId");


--
-- Name: idx_mob_maturities_mob_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mob_maturities_mob_id ON public."MobMaturities" USING btree ("MobId");


--
-- Name: idx_mob_spawn_maturities_maturity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mob_spawn_maturities_maturity_id ON public."MobSpawnMaturities" USING btree ("MaturityId");


--
-- Name: idx_mob_spawn_maturities_spawn_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mob_spawn_maturities_spawn_id ON public."MobSpawnMaturities" USING btree ("AreaId");


--
-- Name: idx_mobloots_item; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mobloots_item ON public."MobLoots" USING btree ("ItemId");


--
-- Name: idx_mobmaturities_mob_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mobmaturities_mob_id ON public."MobMaturities" USING btree ("MobId", "Id");


--
-- Name: idx_mobs_def_prof; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mobs_def_prof ON public."Mobs" USING btree ("DefensiveProfessionId");


--
-- Name: idx_mobs_planet; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mobs_planet ON public."Mobs" USING btree ("PlanetId");


--
-- Name: idx_mobs_scan_prof; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mobs_scan_prof ON public."Mobs" USING btree ("ScanningProfessionId");


--
-- Name: idx_mobs_species; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mobs_species ON public."Mobs" USING btree ("SpeciesId");


--
-- Name: idx_mobspawnmats_area; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mobspawnmats_area ON public."MobSpawnMaturities" USING btree ("AreaId");


--
-- Name: idx_mobspawns_area; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mobspawns_area ON public."MobSpawns" USING btree ("AreaId");


--
-- Name: idx_refiningingredients_itemid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_refiningingredients_itemid ON public."RefiningIngredients" USING btree ("ItemId");


--
-- Name: idx_refiningingredients_itemid_recipeid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_refiningingredients_itemid_recipeid ON public."RefiningIngredients" USING btree ("ItemId", "RecipeId");


--
-- Name: idx_refiningingredients_recipeid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_refiningingredients_recipeid ON public."RefiningIngredients" USING btree ("RecipeId");


--
-- Name: idx_tiermaterials_tierid_materialid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tiermaterials_tierid_materialid ON public."TierMaterials" USING btree ("TierId", "MaterialId");


--
-- Name: idx_tiers_itemid_tier_isarmorset; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tiers_itemid_tier_isarmorset ON public."Tiers" USING btree ("ItemId", "Tier", "IsArmorSet");


--
-- Name: idx_vendoroffers_itemid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendoroffers_itemid ON public."VendorOffers" USING btree ("ItemId");


--
-- Name: idx_vendoroffers_vendorid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendoroffers_vendorid ON public."VendorOffers" USING btree ("VendorId");


--
-- Name: idx_vendoroffers_vendorid_itemid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendoroffers_vendorid_itemid ON public."VendorOffers" USING btree ("VendorId", "ItemId");


--
-- Name: idx_vendors_planetid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendors_planetid ON public."Vendors" USING btree ("PlanetId");


--
-- Name: shops_owner_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX shops_owner_idx ON public."Shops" USING btree ("OwnerId");


--
-- Name: Absorbers Absorbers_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Absorbers_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Absorbers" FOR EACH ROW EXECUTE FUNCTION public."Absorbers_audit_trigger"();


--
-- Name: Areas Areas_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Areas_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Areas" FOR EACH ROW EXECUTE FUNCTION public."Areas_audit_trigger"();


--
-- Name: ArmorPlatings ArmorPlatings_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "ArmorPlatings_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."ArmorPlatings" FOR EACH ROW EXECUTE FUNCTION public."ArmorPlatings_audit_trigger"();


--
-- Name: ArmorSets ArmorSets_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "ArmorSets_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."ArmorSets" FOR EACH ROW EXECUTE FUNCTION public."ArmorSets_audit_trigger"();


--
-- Name: Armors Armors_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Armors_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Armors" FOR EACH ROW EXECUTE FUNCTION public."Armors_audit_trigger"();


--
-- Name: BlueprintBooks BlueprintBooks_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "BlueprintBooks_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."BlueprintBooks" FOR EACH ROW EXECUTE FUNCTION public."BlueprintBooks_audit_trigger"();


--
-- Name: BlueprintDrops BlueprintDrops_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "BlueprintDrops_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."BlueprintDrops" FOR EACH ROW EXECUTE FUNCTION public."BlueprintDrops_audit_trigger"();


--
-- Name: BlueprintMaterials BlueprintMaterials_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "BlueprintMaterials_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."BlueprintMaterials" FOR EACH ROW EXECUTE FUNCTION public."BlueprintMaterials_audit_trigger"();


--
-- Name: BlueprintTypes BlueprintTypes_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "BlueprintTypes_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."BlueprintTypes" FOR EACH ROW EXECUTE FUNCTION public."BlueprintTypes_audit_trigger"();


--
-- Name: Blueprints Blueprints_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Blueprints_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Blueprints" FOR EACH ROW EXECUTE FUNCTION public."Blueprints_audit_trigger"();


--
-- Name: Clothes Clothes_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Clothes_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Clothes" FOR EACH ROW EXECUTE FUNCTION public."Clothes_audit_trigger"();


--
-- Name: Consumables Consumables_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Consumables_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Consumables" FOR EACH ROW EXECUTE FUNCTION public."Consumables_audit_trigger"();


--
-- Name: CreatureControlCapsules CreatureControlCapsules_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "CreatureControlCapsules_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."CreatureControlCapsules" FOR EACH ROW EXECUTE FUNCTION public."CreatureControlCapsules_audit_trigger"();


--
-- Name: Decorations Decorations_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Decorations_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Decorations" FOR EACH ROW EXECUTE FUNCTION public."Decorations_audit_trigger"();


--
-- Name: EffectChips EffectChips_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "EffectChips_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."EffectChips" FOR EACH ROW EXECUTE FUNCTION public."EffectChips_audit_trigger"();


--
-- Name: EffectsOnConsume EffectsOnConsume_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "EffectsOnConsume_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."EffectsOnConsume" FOR EACH ROW EXECUTE FUNCTION public."EffectsOnConsume_audit_trigger"();


--
-- Name: EffectsOnEquip EffectsOnEquip_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "EffectsOnEquip_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."EffectsOnEquip" FOR EACH ROW EXECUTE FUNCTION public."EffectsOnEquip_audit_trigger"();


--
-- Name: EffectsOnSetEquip EffectsOnSetEquip_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "EffectsOnSetEquip_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."EffectsOnSetEquip" FOR EACH ROW EXECUTE FUNCTION public."EffectsOnSetEquip_audit_trigger"();


--
-- Name: EffectsOnUse EffectsOnUse_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "EffectsOnUse_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."EffectsOnUse" FOR EACH ROW EXECUTE FUNCTION public."EffectsOnUse_audit_trigger"();


--
-- Name: Effects Effects_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Effects_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Effects" FOR EACH ROW EXECUTE FUNCTION public."Effects_audit_trigger"();


--
-- Name: EnhancerType EnhancerType_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "EnhancerType_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."EnhancerType" FOR EACH ROW EXECUTE FUNCTION public."EnhancerType_audit_trigger"();


--
-- Name: EquipSetItems EquipSetItems_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "EquipSetItems_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."EquipSetItems" FOR EACH ROW EXECUTE FUNCTION public."EquipSetItems_audit_trigger"();


--
-- Name: EquipSets EquipSets_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "EquipSets_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."EquipSets" FOR EACH ROW EXECUTE FUNCTION public."EquipSets_audit_trigger"();


--
-- Name: EstateSections EstateSections_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "EstateSections_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."EstateSections" FOR EACH ROW EXECUTE FUNCTION public."EstateSections_audit_trigger"();


--
-- Name: Estates Estates_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Estates_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Estates" FOR EACH ROW EXECUTE FUNCTION public."Estates_audit_trigger"();


--
-- Name: Excavators Excavators_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Excavators_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Excavators" FOR EACH ROW EXECUTE FUNCTION public."Excavators_audit_trigger"();


--
-- Name: FinderAmplifiers FinderAmplifiers_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "FinderAmplifiers_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."FinderAmplifiers" FOR EACH ROW EXECUTE FUNCTION public."FinderAmplifiers_audit_trigger"();


--
-- Name: Finders Finders_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Finders_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Finders" FOR EACH ROW EXECUTE FUNCTION public."Finders_audit_trigger"();


--
-- Name: Furniture Furniture_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Furniture_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Furniture" FOR EACH ROW EXECUTE FUNCTION public."Furniture_audit_trigger"();


--
-- Name: Materials Materials_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Materials_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Materials" FOR EACH ROW EXECUTE FUNCTION public."Materials_audit_trigger"();


--
-- Name: MedicalChips MedicalChips_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MedicalChips_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MedicalChips" FOR EACH ROW EXECUTE FUNCTION public."MedicalChips_audit_trigger"();


--
-- Name: MedicalTools MedicalTools_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MedicalTools_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MedicalTools" FOR EACH ROW EXECUTE FUNCTION public."MedicalTools_audit_trigger"();


--
-- Name: MindforceImplants MindforceImplants_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MindforceImplants_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MindforceImplants" FOR EACH ROW EXECUTE FUNCTION public."MindforceImplants_audit_trigger"();


--
-- Name: MiscTools MiscTools_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MiscTools_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MiscTools" FOR EACH ROW EXECUTE FUNCTION public."MiscTools_audit_trigger"();


--
-- Name: MissionChains MissionChains_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MissionChains_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MissionChains" FOR EACH ROW EXECUTE FUNCTION public."MissionChains_audit_trigger"();


--
-- Name: MissionObjectives MissionObjectives_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MissionObjectives_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MissionObjectives" FOR EACH ROW EXECUTE FUNCTION public."MissionObjectives_audit_trigger"();


--
-- Name: MissionPrerequisites MissionPrerequisites_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MissionPrerequisites_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MissionPrerequisites" FOR EACH ROW EXECUTE FUNCTION public."MissionPrerequisites_audit_trigger"();


--
-- Name: MissionRewards MissionRewards_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MissionRewards_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MissionRewards" FOR EACH ROW EXECUTE FUNCTION public."MissionRewards_audit_trigger"();


--
-- Name: Missions Missions_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Missions_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Missions" FOR EACH ROW EXECUTE FUNCTION public."Missions_audit_trigger"();


--
-- Name: MobAttacks MobAttacks_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MobAttacks_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MobAttacks" FOR EACH ROW EXECUTE FUNCTION public."MobAttacks_audit_trigger"();


--
-- Name: MobLoots MobLoots_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MobLoots_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MobLoots" FOR EACH ROW EXECUTE FUNCTION public."MobLoots_audit_trigger"();


--
-- Name: MobMaturities MobMaturities_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MobMaturities_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MobMaturities" FOR EACH ROW EXECUTE FUNCTION public."MobMaturities_audit_trigger"();


--
-- Name: MobSpawnMaturities MobSpawnMaturities_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MobSpawnMaturities_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MobSpawnMaturities" FOR EACH ROW EXECUTE FUNCTION public."MobSpawnMaturities_audit_trigger"();


--
-- Name: MobSpawns MobSpawns_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MobSpawns_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MobSpawns" FOR EACH ROW EXECUTE FUNCTION public."MobSpawns_audit_trigger"();


--
-- Name: MobSpecies MobSpecies_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "MobSpecies_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."MobSpecies" FOR EACH ROW EXECUTE FUNCTION public."MobSpecies_audit_trigger"();


--
-- Name: Mobs Mobs_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Mobs_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Mobs" FOR EACH ROW EXECUTE FUNCTION public."Mobs_audit_trigger"();


--
-- Name: Npcs Npcs_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Npcs_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Npcs" FOR EACH ROW EXECUTE FUNCTION public."Npcs_audit_trigger"();


--
-- Name: PetEffects PetEffects_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "PetEffects_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."PetEffects" FOR EACH ROW EXECUTE FUNCTION public."PetEffects_audit_trigger"();


--
-- Name: Pets Pets_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Pets_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Pets" FOR EACH ROW EXECUTE FUNCTION public."Pets_audit_trigger"();


--
-- Name: Planets Planets_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Planets_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Planets" FOR EACH ROW EXECUTE FUNCTION public."Planets_audit_trigger"();


--
-- Name: ProfessionCategories ProfessionCategories_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "ProfessionCategories_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."ProfessionCategories" FOR EACH ROW EXECUTE FUNCTION public."ProfessionCategories_audit_trigger"();


--
-- Name: ProfessionSkills ProfessionSkills_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "ProfessionSkills_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."ProfessionSkills" FOR EACH ROW EXECUTE FUNCTION public."ProfessionSkills_audit_trigger"();


--
-- Name: Professions Professions_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Professions_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Professions" FOR EACH ROW EXECUTE FUNCTION public."Professions_audit_trigger"();


--
-- Name: Refiners Refiners_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Refiners_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Refiners" FOR EACH ROW EXECUTE FUNCTION public."Refiners_audit_trigger"();


--
-- Name: RefiningIngredients RefiningIngredients_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "RefiningIngredients_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."RefiningIngredients" FOR EACH ROW EXECUTE FUNCTION public."RefiningIngredients_audit_trigger"();


--
-- Name: RefiningRecipes RefiningRecipes_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "RefiningRecipes_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."RefiningRecipes" FOR EACH ROW EXECUTE FUNCTION public."RefiningRecipes_audit_trigger"();


--
-- Name: Scanners Scanners_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Scanners_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Scanners" FOR EACH ROW EXECUTE FUNCTION public."Scanners_audit_trigger"();


--
-- Name: Shops Shops_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Shops_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Shops" FOR EACH ROW EXECUTE FUNCTION public."Shops_audit_trigger"();


--
-- Name: Signs Signs_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Signs_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Signs" FOR EACH ROW EXECUTE FUNCTION public."Signs_audit_trigger"();


--
-- Name: SkillCategories SkillCategories_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "SkillCategories_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."SkillCategories" FOR EACH ROW EXECUTE FUNCTION public."SkillCategories_audit_trigger"();


--
-- Name: SkillUnlocks SkillUnlocks_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "SkillUnlocks_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."SkillUnlocks" FOR EACH ROW EXECUTE FUNCTION public."SkillUnlocks_audit_trigger"();


--
-- Name: Skills Skills_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Skills_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Skills" FOR EACH ROW EXECUTE FUNCTION public."Skills_audit_trigger"();


--
-- Name: StorageContainers StorageContainers_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "StorageContainers_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."StorageContainers" FOR EACH ROW EXECUTE FUNCTION public."StorageContainers_audit_trigger"();


--
-- Name: StrongboxLoots StrongboxLoots_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "StrongboxLoots_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."StrongboxLoots" FOR EACH ROW EXECUTE FUNCTION public."StrongboxLoots_audit_trigger"();


--
-- Name: Strongboxes Strongboxes_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Strongboxes_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Strongboxes" FOR EACH ROW EXECUTE FUNCTION public."Strongboxes_audit_trigger"();


--
-- Name: TeleportationChips TeleportationChips_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "TeleportationChips_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."TeleportationChips" FOR EACH ROW EXECUTE FUNCTION public."TeleportationChips_audit_trigger"();


--
-- Name: Teleporters Teleporters_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Teleporters_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Teleporters" FOR EACH ROW EXECUTE FUNCTION public."Teleporters_audit_trigger"();


--
-- Name: TierMaterials TierMaterials_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "TierMaterials_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."TierMaterials" FOR EACH ROW EXECUTE FUNCTION public."TierMaterials_audit_trigger"();


--
-- Name: Tiers Tiers_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Tiers_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Tiers" FOR EACH ROW EXECUTE FUNCTION public."Tiers_audit_trigger"();


--
-- Name: VehicleAttachmentSlots VehicleAttachmentSlots_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "VehicleAttachmentSlots_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."VehicleAttachmentSlots" FOR EACH ROW EXECUTE FUNCTION public."VehicleAttachmentSlots_audit_trigger"();


--
-- Name: VehicleAttachmentTypes VehicleAttachmentTypes_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "VehicleAttachmentTypes_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."VehicleAttachmentTypes" FOR EACH ROW EXECUTE FUNCTION public."VehicleAttachmentTypes_audit_trigger"();


--
-- Name: Vehicles Vehicles_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Vehicles_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Vehicles" FOR EACH ROW EXECUTE FUNCTION public."Vehicles_audit_trigger"();


--
-- Name: VendorOfferPrices VendorOfferPrices_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "VendorOfferPrices_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."VendorOfferPrices" FOR EACH ROW EXECUTE FUNCTION public."VendorOfferPrices_audit_trigger"();


--
-- Name: VendorOffers VendorOffers_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "VendorOffers_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."VendorOffers" FOR EACH ROW EXECUTE FUNCTION public."VendorOffers_audit_trigger"();


--
-- Name: Vendors Vendors_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Vendors_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Vendors" FOR EACH ROW EXECUTE FUNCTION public."Vendors_audit_trigger"();


--
-- Name: WeaponAmplifiers WeaponAmplifiers_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "WeaponAmplifiers_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."WeaponAmplifiers" FOR EACH ROW EXECUTE FUNCTION public."WeaponAmplifiers_audit_trigger"();


--
-- Name: WeaponVisionAttachments WeaponVisionAttachments_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "WeaponVisionAttachments_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."WeaponVisionAttachments" FOR EACH ROW EXECUTE FUNCTION public."WeaponVisionAttachments_audit_trigger"();


--
-- Name: Weapons Weapons_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER "Weapons_audit_trigger" AFTER INSERT OR DELETE OR UPDATE ON public."Weapons" FOR EACH ROW EXECUTE FUNCTION public."Weapons_audit_trigger"();


--
-- Name: Shops shops_audit_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER shops_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON public."Shops" FOR EACH ROW EXECUTE FUNCTION public.shops_audit_trigger();


--
-- Name: Areas update_coordinates_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_coordinates_trigger BEFORE INSERT OR UPDATE OF "Shape", "Data" ON public."Areas" FOR EACH ROW EXECUTE FUNCTION public.update_coordinates();


--
-- Name: Areas Areas_PlanetId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Areas"
    ADD CONSTRAINT "Areas_PlanetId_fkey" FOREIGN KEY ("PlanetId") REFERENCES public."Planets"("Id");


--
-- Name: Armors Armors_SetId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Armors"
    ADD CONSTRAINT "Armors_SetId_fkey" FOREIGN KEY ("SetId") REFERENCES public."ArmorSets"("Id") NOT VALID;


--
-- Name: BlueprintMaterials BlueprintMaterials_BlueprintId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."BlueprintMaterials"
    ADD CONSTRAINT "BlueprintMaterials_BlueprintId_fkey" FOREIGN KEY ("BlueprintId") REFERENCES public."Blueprints"("Id") ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;


--
-- Name: Blueprints Blueprints_ProfessionId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Blueprints"
    ADD CONSTRAINT "Blueprints_ProfessionId_fkey" FOREIGN KEY ("ProfessionId") REFERENCES public."Professions"("Id") NOT VALID;


--
-- Name: EquipSetItems EquipSetItems_EquipSetId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."EquipSetItems"
    ADD CONSTRAINT "EquipSetItems_EquipSetId_fkey" FOREIGN KEY ("EquipSetId") REFERENCES public."EquipSets"("Id") ON DELETE CASCADE NOT VALID;


--
-- Name: MobAttacks MobAttacks_MaturityId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobAttacks"
    ADD CONSTRAINT "MobAttacks_MaturityId_fkey" FOREIGN KEY ("MaturityId") REFERENCES public."MobMaturities"("Id") ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;


--
-- Name: MobLoots MobLoots_MaturityId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobLoots"
    ADD CONSTRAINT "MobLoots_MaturityId_fkey" FOREIGN KEY ("MaturityId") REFERENCES public."MobMaturities"("Id") ON UPDATE CASCADE ON DELETE SET NULL NOT VALID;


--
-- Name: MobLoots MobLoots_MobId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobLoots"
    ADD CONSTRAINT "MobLoots_MobId_fkey" FOREIGN KEY ("MobId") REFERENCES public."Mobs"("Id") ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;


--
-- Name: MobMaturities MobMaturities_MobId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobMaturities"
    ADD CONSTRAINT "MobMaturities_MobId_fkey" FOREIGN KEY ("MobId") REFERENCES public."Mobs"("Id") ON DELETE CASCADE;


--
-- Name: MobSpawnMaturities MobSpawnMaturities_AreaId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobSpawnMaturities"
    ADD CONSTRAINT "MobSpawnMaturities_AreaId_fkey" FOREIGN KEY ("AreaId") REFERENCES public."Areas"("Id") ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;


--
-- Name: MobSpawnMaturities MobSpawnMaturities_MaturityId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobSpawnMaturities"
    ADD CONSTRAINT "MobSpawnMaturities_MaturityId_fkey" FOREIGN KEY ("MaturityId") REFERENCES public."MobMaturities"("Id") ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;


--
-- Name: MobSpawns MobSpawns_AreaId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."MobSpawns"
    ADD CONSTRAINT "MobSpawns_AreaId_fkey" FOREIGN KEY ("AreaId") REFERENCES public."Areas"("Id") ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: Mobs Mobs_SpeciesId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Mobs"
    ADD CONSTRAINT "Mobs_SpeciesId_fkey" FOREIGN KEY ("SpeciesId") REFERENCES public."MobSpecies"("Id") ON UPDATE CASCADE ON DELETE SET NULL NOT VALID;


--
-- Name: Npcs Npcs_PlanetId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Npcs"
    ADD CONSTRAINT "Npcs_PlanetId_fkey" FOREIGN KEY ("PlanetId") REFERENCES public."Planets"("Id") ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: PetEffects PetEffects_PetId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."PetEffects"
    ADD CONSTRAINT "PetEffects_PetId_fkey" FOREIGN KEY ("PetId") REFERENCES public."Pets"("Id") ON DELETE CASCADE NOT VALID;


--
-- Name: Shops Shops_EstateId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Shops"
    ADD CONSTRAINT "Shops_EstateId_fkey" FOREIGN KEY ("EstateId") REFERENCES public."Estates"("Id") ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;


--
-- Name: TierMaterials TierMaterials_TierId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."TierMaterials"
    ADD CONSTRAINT "TierMaterials_TierId_fkey" FOREIGN KEY ("TierId") REFERENCES public."Tiers"("Id") ON DELETE CASCADE NOT VALID;


--
-- Name: VendorOfferPrices VendorOfferPrices_OfferId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VendorOfferPrices"
    ADD CONSTRAINT "VendorOfferPrices_OfferId_fkey" FOREIGN KEY ("OfferId") REFERENCES public."VendorOffers"("Id") ON DELETE CASCADE NOT VALID;


--
-- Name: VendorOffers VendorOffers_VendorId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VendorOffers"
    ADD CONSTRAINT "VendorOffers_VendorId_fkey" FOREIGN KEY ("VendorId") REFERENCES public."Vendors"("Id") ON DELETE CASCADE NOT VALID;


--
-- Name: Weapons Weapons_AttachmentTypeId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Weapons"
    ADD CONSTRAINT "Weapons_AttachmentTypeId_fkey" FOREIGN KEY ("AttachmentTypeId") REFERENCES public."VehicleAttachmentTypes"("Id") NOT VALID;


--
-- Name: Weapons Weapons_PlanetId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Weapons"
    ADD CONSTRAINT "Weapons_PlanetId_fkey" FOREIGN KEY ("PlanetId") REFERENCES public."Planets"("Id") NOT VALID;


--
-- PostgreSQL database dump complete
--


-- ==========================================================================
-- PERMISSIONS
-- ==========================================================================

-- Restore search_path for unqualified GRANT targets
SET search_path = public;

-- nexus role: read access to all tables (web application)
GRANT SELECT ON "Absorbers" TO nexus;
GRANT SELECT ON "Areas" TO nexus;
GRANT SELECT ON "ArmorPlatings" TO nexus;
GRANT SELECT ON "ArmorSets" TO nexus;
GRANT SELECT ON "Armors" TO nexus;
GRANT SELECT ON "EnhancerType" TO nexus;
GRANT SELECT ON "FinderAmplifiers" TO nexus;
GRANT SELECT ON "MindforceImplants" TO nexus;
GRANT SELECT ON "WeaponAmplifiers" TO nexus;
GRANT SELECT ON "WeaponVisionAttachments" TO nexus;
GRANT SELECT ON "BlueprintBooks" TO nexus;
GRANT SELECT ON "BlueprintDrops" TO nexus;
GRANT SELECT ON "BlueprintMaterials" TO nexus;
GRANT SELECT ON "BlueprintTypes" TO nexus;
GRANT SELECT ON "Blueprints" TO nexus;
GRANT SELECT ON "Clothes" TO nexus;
GRANT SELECT ON "Consumables" TO nexus;
GRANT SELECT ON "CreatureControlCapsules" TO nexus;
GRANT SELECT ON "Decorations" TO nexus;
GRANT SELECT ON "EffectChips" TO nexus;
GRANT SELECT ON "Effects" TO nexus;
GRANT SELECT ON "EffectsOnConsume" TO nexus;
GRANT SELECT ON "EffectsOnEquip" TO nexus;
GRANT SELECT ON "EffectsOnSetEquip" TO nexus;
GRANT SELECT ON "EffectsOnUse" TO nexus;
GRANT SELECT ON "EquipSetItems" TO nexus;
GRANT SELECT ON "EquipSets" TO nexus;
GRANT SELECT ON "EstateSections" TO nexus;
GRANT SELECT ON "Estates" TO nexus;
GRANT SELECT ON "Excavators" TO nexus;
GRANT SELECT ON "Finders" TO nexus;
GRANT SELECT ON "Furniture" TO nexus;
GRANT SELECT ON "Signs" TO nexus;
GRANT SELECT ON "StorageContainers" TO nexus;
GRANT SELECT ON "ItemTags" TO nexus;
GRANT SELECT ON "Materials" TO nexus;
GRANT SELECT ON "MedicalChips" TO nexus;
GRANT SELECT ON "MedicalTools" TO nexus;
GRANT SELECT ON "MiscTools" TO nexus;
GRANT SELECT ON "Pets" TO nexus;
GRANT SELECT ON "Refiners" TO nexus;
GRANT SELECT ON "Scanners" TO nexus;
GRANT SELECT ON "TeleportationChips" TO nexus;
GRANT SELECT ON "Vehicles" TO nexus;
GRANT SELECT ON "Weapons" TO nexus;
GRANT SELECT ON "Teleporters" TO nexus;
GRANT SELECT ON "Planets" TO nexus;
GRANT SELECT ON "MissionChains" TO nexus;
GRANT SELECT ON "MissionObjectives" TO nexus;
GRANT SELECT ON "MissionPrerequisites" TO nexus;
GRANT SELECT ON "MissionRewards" TO nexus;
GRANT SELECT ON "Missions" TO nexus;
GRANT SELECT ON "MobAttacks" TO nexus;
GRANT SELECT ON "MobLoots" TO nexus;
GRANT SELECT ON "MobMaturities" TO nexus;
GRANT SELECT ON "MobSpawnMaturities" TO nexus;
GRANT SELECT ON "MobSpawns" TO nexus;
GRANT SELECT ON "MobSpecies" TO nexus;
GRANT SELECT ON "Mobs" TO nexus;
GRANT SELECT ON "Npcs" TO nexus;
GRANT SELECT ON "PetEffects" TO nexus;
GRANT SELECT ON "ProfessionCategories" TO nexus;
GRANT SELECT ON "ProfessionSkills" TO nexus;
GRANT SELECT ON "Professions" TO nexus;
GRANT SELECT ON "RefiningIngredients" TO nexus;
GRANT SELECT ON "RefiningRecipes" TO nexus;
GRANT SELECT ON "Shops" TO nexus;
GRANT SELECT ON "SkillCategories" TO nexus;
GRANT SELECT ON "SkillUnlocks" TO nexus;
GRANT SELECT ON "Skills" TO nexus;
GRANT SELECT ON "StrongboxLoots" TO nexus;
GRANT SELECT ON "Strongboxes" TO nexus;
GRANT SELECT ON "Tags" TO nexus;
GRANT SELECT ON "TierMaterials" TO nexus;
GRANT SELECT ON "Tiers" TO nexus;
GRANT SELECT ON "VehicleAttachmentSlots" TO nexus;
GRANT SELECT ON "VehicleAttachmentTypes" TO nexus;
GRANT SELECT ON "VendorOfferPrices" TO nexus;
GRANT SELECT ON "VendorOffers" TO nexus;
GRANT SELECT ON "Vendors" TO nexus;

-- nexus role: read access to audit tables
GRANT SELECT ON "Absorbers_audit" TO nexus;
GRANT SELECT ON "Areas_audit" TO nexus;
GRANT SELECT ON "ArmorPlatings_audit" TO nexus;
GRANT SELECT ON "ArmorSets_audit" TO nexus;
GRANT SELECT ON "Armors_audit" TO nexus;
GRANT SELECT ON "BlueprintBooks_audit" TO nexus;
GRANT SELECT ON "BlueprintDrops_audit" TO nexus;
GRANT SELECT ON "BlueprintMaterials_audit" TO nexus;
GRANT SELECT ON "BlueprintTypes_audit" TO nexus;
GRANT SELECT ON "Blueprints_audit" TO nexus;
GRANT SELECT ON "Clothes_audit" TO nexus;
GRANT SELECT ON "Consumables_audit" TO nexus;
GRANT SELECT ON "CreatureControlCapsules_audit" TO nexus;
GRANT SELECT ON "Decorations_audit" TO nexus;
GRANT SELECT ON "EffectChips_audit" TO nexus;
GRANT SELECT ON "EffectsOnConsume_audit" TO nexus;
GRANT SELECT ON "EffectsOnEquip_audit" TO nexus;
GRANT SELECT ON "EffectsOnSetEquip_audit" TO nexus;
GRANT SELECT ON "EffectsOnUse_audit" TO nexus;
GRANT SELECT ON "Effects_audit" TO nexus;
GRANT SELECT ON "EnhancerType_audit" TO nexus;
GRANT SELECT ON "EquipSetItems_audit" TO nexus;
GRANT SELECT ON "EquipSets_audit" TO nexus;
GRANT SELECT ON "EstateSections_audit" TO nexus;
GRANT SELECT ON "Estates_audit" TO nexus;
GRANT SELECT ON "Excavators_audit" TO nexus;
GRANT SELECT ON "FinderAmplifiers_audit" TO nexus;
GRANT SELECT ON "Finders_audit" TO nexus;
GRANT SELECT ON "Furniture_audit" TO nexus;
GRANT SELECT ON "Materials_audit" TO nexus;
GRANT SELECT ON "MedicalChips_audit" TO nexus;
GRANT SELECT ON "MedicalTools_audit" TO nexus;
GRANT SELECT ON "MindforceImplants_audit" TO nexus;
GRANT SELECT ON "MiscTools_audit" TO nexus;
GRANT SELECT ON "MissionChains_audit" TO nexus;
GRANT SELECT ON "MissionObjectives_audit" TO nexus;
GRANT SELECT ON "MissionPrerequisites_audit" TO nexus;
GRANT SELECT ON "MissionRewards_audit" TO nexus;
GRANT SELECT ON "Missions_audit" TO nexus;
GRANT SELECT ON "MobAttacks_audit" TO nexus;
GRANT SELECT ON "MobLoots_audit" TO nexus;
GRANT SELECT ON "MobMaturities_audit" TO nexus;
GRANT SELECT ON "MobSpawnMaturities_audit" TO nexus;
GRANT SELECT ON "MobSpawns_audit" TO nexus;
GRANT SELECT ON "MobSpecies_audit" TO nexus;
GRANT SELECT ON "Mobs_audit" TO nexus;
GRANT SELECT ON "Npcs_audit" TO nexus;
GRANT SELECT ON "PetEffects_audit" TO nexus;
GRANT SELECT ON "Pets_audit" TO nexus;
GRANT SELECT ON "Planets_audit" TO nexus;
GRANT SELECT ON "ProfessionCategories_audit" TO nexus;
GRANT SELECT ON "ProfessionSkills_audit" TO nexus;
GRANT SELECT ON "Professions_audit" TO nexus;
GRANT SELECT ON "Refiners_audit" TO nexus;
GRANT SELECT ON "RefiningIngredients_audit" TO nexus;
GRANT SELECT ON "RefiningRecipes_audit" TO nexus;
GRANT SELECT ON "Scanners_audit" TO nexus;
GRANT SELECT ON "Shops_audit" TO nexus;
GRANT SELECT ON "Signs_audit" TO nexus;
GRANT SELECT ON "SkillCategories_audit" TO nexus;
GRANT SELECT ON "SkillUnlocks_audit" TO nexus;
GRANT SELECT ON "Skills_audit" TO nexus;
GRANT SELECT ON "StorageContainers_audit" TO nexus;
GRANT SELECT ON "StrongboxLoots_audit" TO nexus;
GRANT SELECT ON "Strongboxes_audit" TO nexus;
GRANT SELECT ON "TeleportationChips_audit" TO nexus;
GRANT SELECT ON "Teleporters_audit" TO nexus;
GRANT SELECT ON "TierMaterials_audit" TO nexus;
GRANT SELECT ON "Tiers_audit" TO nexus;
GRANT SELECT ON "VehicleAttachmentSlots_audit" TO nexus;
GRANT SELECT ON "VehicleAttachmentTypes_audit" TO nexus;
GRANT SELECT ON "Vehicles_audit" TO nexus;
GRANT SELECT ON "VendorOfferPrices_audit" TO nexus;
GRANT SELECT ON "VendorOffers_audit" TO nexus;
GRANT SELECT ON "Vendors_audit" TO nexus;
GRANT SELECT ON "WeaponAmplifiers_audit" TO nexus;
GRANT SELECT ON "WeaponVisionAttachments_audit" TO nexus;
GRANT SELECT ON "Weapons_audit" TO nexus;

-- nexus role: sequence usage
GRANT USAGE, SELECT ON SEQUENCE "Absorbers_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Areas_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "ArmorPlatings_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "ArmorSets_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Armors_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "BlueprintBooks_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "BlueprintTypes_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Blueprints_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Clothes_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Consumables_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "CreatureControlCapsules_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Decorations_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "EffectChips_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Effects_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "EnhancerType_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "EquipSets_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "EstateSections_EstateId_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Estates_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Excavators_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "FinderAmplifiers_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Finders_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Furniture_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Maps_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Materials_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "MedicalChips_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "MedicalTools_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "MindforceImplants_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "MiscTools_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "MissionChains_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "MissionObjectives_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Missions_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "MobMaturities_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "MobSpecies_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Mobs_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Npcs_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Pets_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "ProfessionCategories_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Professions_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Refiners_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "RefiningRecipes_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Scanners_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Signs_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "SkillCategories_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Skills_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "StorageContainers_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Strongboxes_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Tags_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "TeleportationChips_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Teleporters_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Tiers_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "VehicleAttachmentType_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Vehicles_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "VendorOffers_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Vendors_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "WeaponAmplifiers_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "WeaponVisionAttachments_Id_seq" TO nexus;
GRANT USAGE, SELECT ON SEQUENCE "Weapons_Id_seq" TO nexus;

-- nexus_bot role: no initial grants (added by migration 001_bot_permissions_nexus.sql)
