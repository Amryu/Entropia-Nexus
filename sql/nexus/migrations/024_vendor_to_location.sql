-- Migration 024: Consolidate Vendors into Locations
-- Migrates Vendor data to Locations table (enum value added in 023),
-- reparents VendorOffers FK from Vendors to Locations, drops old Vendors table.

-- 1. Migrate Vendors → Locations (auto-generated IDs to avoid clashes)
--    Use a temp mapping table to track old Vendor ID → new Location ID
CREATE TEMP TABLE vendor_id_map AS
WITH inserted AS (
  INSERT INTO "Locations" ("Name", "Type", "Description", "PlanetId", "Longitude", "Latitude", "Altitude")
  SELECT "Name", 'Vendor'::"LocationType", "Description", "PlanetId", "Longitude", "Latitude", "Altitude"
  FROM ONLY "Vendors"
  ORDER BY "Id"
  RETURNING "Id", "Name"
)
SELECT v."Id" AS old_id, i."Id" AS new_id
FROM inserted i
JOIN ONLY "Vendors" v ON v."Name" = i."Name";

-- 2. Drop old FK from VendorOffers to Vendors
ALTER TABLE "VendorOffers" DROP CONSTRAINT "VendorOffers_VendorId_fkey";

-- 3. Remap VendorOffers to new Location IDs
UPDATE ONLY "VendorOffers" vo
SET "VendorId" = m.new_id
FROM vendor_id_map m
WHERE vo."VendorId" = m.old_id;

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

-- 8. Clean up
DROP TABLE IF EXISTS vendor_id_map;
