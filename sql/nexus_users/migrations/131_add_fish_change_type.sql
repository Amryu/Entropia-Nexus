-- Migration: Add Fish / FishingRod / FishingReel / FishingBlank / FishingLine / FishingLure change entity types
-- Database: nexus_users
-- Date: 2026-04-15

ALTER TYPE change_entity ADD VALUE IF NOT EXISTS 'Fish';
ALTER TYPE change_entity ADD VALUE IF NOT EXISTS 'FishingRod';
ALTER TYPE change_entity ADD VALUE IF NOT EXISTS 'FishingReel';
ALTER TYPE change_entity ADD VALUE IF NOT EXISTS 'FishingBlank';
ALTER TYPE change_entity ADD VALUE IF NOT EXISTS 'FishingLine';
ALTER TYPE change_entity ADD VALUE IF NOT EXISTS 'FishingLure';
