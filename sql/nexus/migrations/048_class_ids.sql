BEGIN;

-- Centralized lookup table mapping entities to their in-game ClassId
CREATE TABLE "ClassIds" (
  "Id" SERIAL PRIMARY KEY,
  "EntityType" TEXT NOT NULL,
  "EntityId" INTEGER NOT NULL,
  "ClassId" BIGINT NOT NULL,
  UNIQUE ("EntityType", "EntityId"),
  UNIQUE ("ClassId")
);

CREATE INDEX "ClassIds_classid_idx" ON "ClassIds" ("ClassId");

-- Audit table (PostgreSQL inheritance pattern)
CREATE TABLE "ClassIds_audit" (
  "Id" INTEGER DEFAULT NULL,
  operation CHAR(1) NOT NULL,
  stamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  userid TEXT NOT NULL
) INHERITS ("ClassIds");

-- Audit trigger function
CREATE OR REPLACE FUNCTION "ClassIds_audit_trigger"() RETURNS TRIGGER AS $$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "ClassIds_audit" SELECT OLD.*, 'D', now(), current_user;
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "ClassIds_audit" SELECT NEW.*, 'U', now(), current_user;
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "ClassIds_audit" SELECT NEW.*, 'I', now(), current_user;
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER "ClassIds_audit_trigger"
AFTER INSERT OR UPDATE OR DELETE ON "ClassIds"
FOR EACH ROW EXECUTE FUNCTION "ClassIds_audit_trigger"();

-- TableChanges tracking
CREATE TRIGGER zz_track_change
AFTER INSERT OR UPDATE OR DELETE ON "ClassIds"
FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();

-- Permissions
GRANT SELECT ON "ClassIds" TO nexus;
GRANT SELECT, INSERT, UPDATE, DELETE ON "ClassIds" TO nexus_bot;
GRANT USAGE, SELECT ON SEQUENCE "ClassIds_Id_seq" TO nexus_bot;
GRANT SELECT ON "ClassIds_audit" TO nexus;
GRANT INSERT ON "ClassIds_audit" TO nexus_bot;

COMMIT;
