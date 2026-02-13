-- Migration 023: Add 'Vendor' to LocationType enum
-- Must be committed separately before the value can be used in DML (PG requirement).
ALTER TYPE "LocationType" ADD VALUE IF NOT EXISTS 'Vendor';
