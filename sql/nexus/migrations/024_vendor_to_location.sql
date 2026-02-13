-- Migration 024: Consolidate Vendors into Locations
-- Migrates Vendor data to Locations table (enum value added in 023),
-- reparents VendorOffers FK from Vendors to Locations, drops old Vendors table.

-- 1. Migrate Vendors → Locations (preserving IDs)
INSERT INTO ONLY "Locations" ("Id", "Name", "Type", "Description", "PlanetId", "Longitude", "Latitude", "Altitude")
SELECT "Id", "Name", 'Vendor'::"LocationType", "Description", "PlanetId", "Longitude", "Latitude", "Altitude"
FROM ONLY "Vendors";

-- 2. Update Locations sequence to account for migrated Vendor IDs
SELECT setval('"Locations_Id_seq"', GREATEST(
  (SELECT COALESCE(MAX("Id"), 0) FROM ONLY "Locations"),
  (SELECT last_value FROM "Locations_Id_seq")
));

-- 3. Drop old FK from VendorOffers to Vendors
ALTER TABLE "VendorOffers" DROP CONSTRAINT "VendorOffers_VendorId_fkey";

-- 4. Rename VendorOffers.VendorId → LocationId (propagates to audit table via inheritance)
ALTER TABLE "VendorOffers" RENAME COLUMN "VendorId" TO "LocationId";

-- 5. Add new FK from VendorOffers(LocationId) to Locations(Id)
ALTER TABLE ONLY "VendorOffers" ADD CONSTRAINT "VendorOffers_LocationId_fkey"
  FOREIGN KEY ("LocationId") REFERENCES "Locations"("Id") ON DELETE CASCADE;

-- 6. Rename unique constraint and indexes for clarity
ALTER INDEX "VendorOffers_ItemId_VendorId_key" RENAME TO "VendorOffers_ItemId_LocationId_key";
ALTER INDEX idx_vendoroffers_vendorid RENAME TO idx_vendoroffers_locationid;
ALTER INDEX idx_vendoroffers_vendorid_itemid RENAME TO idx_vendoroffers_locationid_itemid;

-- 7. Drop old Vendors tables (audit inherits, so drop child first)
DROP TABLE IF EXISTS "Vendors_audit";
DROP TABLE IF EXISTS "Vendors" CASCADE;
DROP SEQUENCE IF EXISTS "Vendors_Id_seq";
