-- Migration: Add 'Chemistry' to BlueprintType enum
-- Description: Adds the Chemistry blueprint type for chemical crafting blueprints
-- Database: nexus
-- Date: 2026-02-24

ALTER TYPE "BlueprintType" ADD VALUE IF NOT EXISTS 'Chemistry';
