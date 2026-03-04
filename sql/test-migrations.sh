#!/usr/bin/env bash
# ============================================================================
# Migration Validation Script
# ============================================================================
# Validates that 000_init.sql + all migrations produce the same schema as the
# current production databases.
#
# Compares structural elements (tables, columns, types, indexes, constraints,
# triggers, functions) by querying information_schema — not raw pg_dump text.
# This avoids false positives from whitespace/formatting differences in
# trigger function bodies.
#
# Known limitations:
# - Some migrations mix DDL + DML in a single transaction. When the DML fails
#   (no seed data), the DDL rolls back too.
# - Migration 030 uses ALTER TABLE ONLY ... ADD COLUMN which is incompatible
#   with PostgreSQL table inheritance.
#
# Usage:
#   bash sql/test-migrations.sh [--keep] [--nexus-only] [--users-only]
#
#   --keep         Don't drop temp databases after test
#   --nexus-only   Only test the nexus database
#   --users-only   Only test the nexus_users database
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMPDIR="${TMPDIR:-/tmp}"

# --- Parse arguments --------------------------------------------------------

KEEP=false
TEST_NEXUS=true
TEST_USERS=true

for arg in "$@"; do
  case "$arg" in
    --keep)       KEEP=true ;;
    --nexus-only) TEST_USERS=false ;;
    --users-only) TEST_NEXUS=false ;;
    *)            echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

# --- Database credentials ---------------------------------------------------

export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-postgres}"
export PGPASSWORD="${PGPASSWORD:-***REMOVED***}"

PASS_COUNT=0
FAIL_COUNT=0

# --- Helpers ----------------------------------------------------------------

log()  { echo -e "\n\033[1;34m==>\033[0m $*"; }
ok()   { echo -e "\033[1;32m  PASS\033[0m $*"; }
fail() { echo -e "\033[1;31m  FAIL\033[0m $*"; }
warn() { echo -e "\033[1;33m  WARN\033[0m $*"; }

recreate_db() {
  local db="$1"
  log "Dropping and creating $db ..."
  psql -q -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$db' AND pid <> pg_backend_pid();" \
    > /dev/null 2>&1 || true
  psql -q -d postgres -c "DROP DATABASE IF EXISTS \"$db\";" 2>/dev/null
  psql -q -d postgres -c "CREATE DATABASE \"$db\";"
}

apply_sql_strict() {
  local db="$1" file="$2"
  psql -q -v ON_ERROR_STOP=1 -d "$db" -f "$file" > /dev/null
}

apply_sql_lenient() {
  local db="$1" file="$2" errlog="$3"
  psql -q -d "$db" -f "$file" > /dev/null 2>>"$errlog"
  return 0
}

seed_reference_data() {
  local prod_db="$1" test_db="$2" table="$3"
  pg_dump --data-only --no-owner --no-acl --disable-triggers -t "\"$table\"" -d "$prod_db" \
    | psql -q -d "$test_db" > /dev/null 2>&1
}

# --- Structural comparison queries -----------------------------------------
# Each query returns a sorted text fingerprint of a schema aspect.

# Tables: name, kind (ordinary/inherited)
query_tables() {
  psql -d "$1" -t -A -c "
    SELECT c.relname, CASE WHEN EXISTS(SELECT 1 FROM pg_inherits WHERE inhrelid = c.oid) THEN 'inherits' ELSE 'table' END
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname NOT LIKE 'spatial_%'
    ORDER BY c.relname;
  "
}

# Columns: table, column, type, nullable, default, position
query_columns() {
  psql -d "$1" -t -A -c "
    SELECT table_name, column_name, data_type,
           COALESCE(udt_name, ''), is_nullable,
           COALESCE(column_default, ''), ordinal_position
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name NOT LIKE 'spatial_%'
    ORDER BY table_name, ordinal_position;
  "
}

# Enum types: name + values
query_types() {
  psql -d "$1" -t -A -c "
    SELECT t.typname, string_agg(e.enumlabel, ',' ORDER BY e.enumsortorder)
    FROM pg_type t
    JOIN pg_enum e ON e.enumtypid = t.oid
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'public'
    GROUP BY t.typname ORDER BY t.typname;
  "
}

# Indexes: name, table, columns, unique
query_indexes() {
  psql -d "$1" -t -A -c "
    SELECT i.relname, t.relname,
           pg_get_indexdef(ix.indexrelid),
           ix.indisunique
    FROM pg_index ix
    JOIN pg_class i ON i.oid = ix.indexrelid
    JOIN pg_class t ON t.oid = ix.indrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'public' AND t.relname NOT LIKE 'spatial_%'
    ORDER BY t.relname, i.relname;
  "
}

# Constraints: name, table, type, definition
query_constraints() {
  psql -d "$1" -t -A -c "
    SELECT conname, c.relname, contype, pg_get_constraintdef(con.oid)
    FROM pg_constraint con
    JOIN pg_class c ON c.oid = con.conrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname NOT LIKE 'spatial_%'
    ORDER BY c.relname, conname;
  "
}

# Triggers: name, table, function
query_triggers() {
  psql -d "$1" -t -A -c "
    SELECT t.tgname, c.relname, p.proname
    FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_proc p ON p.oid = t.tgfoid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND NOT t.tgisinternal AND c.relname NOT LIKE 'spatial_%'
    ORDER BY c.relname, t.tgname;
  "
}

# Functions: name, args, return type (NOT body — avoids formatting diffs)
query_functions() {
  psql -d "$1" -t -A -c "
    SELECT p.proname, pg_get_function_arguments(p.oid), pg_get_function_result(p.oid)
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
    ORDER BY p.proname, pg_get_function_arguments(p.oid);
  "
}

# Sequences: name, owned by
query_sequences() {
  psql -d "$1" -t -A -c "
    SELECT s.relname,
           COALESCE(d.refobjid::regclass::text, '')
    FROM pg_class s
    JOIN pg_namespace n ON n.oid = s.relnamespace
    LEFT JOIN pg_depend d ON d.objid = s.oid AND d.deptype = 'a'
    WHERE n.nspname = 'public' AND s.relkind = 'S'
    ORDER BY s.relname;
  "
}

# Views: name, definition
query_views() {
  psql -d "$1" -t -A -c "
    SELECT viewname, regexp_replace(definition, '\s+', ' ', 'g')
    FROM pg_views WHERE schemaname = 'public'
    ORDER BY viewname;
  "
}

# Compare one aspect; returns 0 if match, 1 if differ
compare_aspect() {
  local aspect="$1" prod_db="$2" test_db="$3" diff_file="$4"
  local prod_out="$TMPDIR/cmp_prod_${aspect}.txt"
  local test_out="$TMPDIR/cmp_test_${aspect}.txt"

  "query_${aspect}" "$prod_db" > "$prod_out" 2>/dev/null
  "query_${aspect}" "$test_db" > "$test_out" 2>/dev/null

  if diff -u "$prod_out" "$test_out" >> "$diff_file" 2>&1; then
    ok "  $aspect"
    rm -f "$prod_out" "$test_out"
    return 0
  else
    fail "  $aspect (see diff below)"
    # Show a concise summary
    local only_prod only_test
    only_prod=$(diff "$prod_out" "$test_out" | grep '^< ' | wc -l)
    only_test=$(diff "$prod_out" "$test_out" | grep '^> ' | wc -l)
    echo "      Production only: $only_prod items, Test only: $only_test items"
    diff "$prod_out" "$test_out" | grep '^[<>]' | head -15 | sed 's/^/      /'
    rm -f "$prod_out" "$test_out"
    return 1
  fi
}

# --- Main test function -----------------------------------------------------

test_database() {
  local name="$1"
  local init_sql="$2"
  local migrations_dir="$3"
  local prod_db="$4"
  local temp_db="${name}_mig_test"
  local errlog="$TMPDIR/${name}_migration_errors.log"
  local diff_file="$TMPDIR/${name}_structural_diff.txt"

  log "Testing $name: init + migrations vs production schema"
  > "$errlog"
  > "$diff_file"

  # 1. Create temp database
  recreate_db "$temp_db"

  # 2. Run init script (strict)
  log "Applying init script ..."
  if ! apply_sql_strict "$temp_db" "$init_sql"; then
    fail "$name: init script failed!"
    psql -v ON_ERROR_STOP=1 -d "$temp_db" -f "$init_sql" 2>&1 | tail -10 || true
    FAIL_COUNT=$((FAIL_COUNT + 1))
    if ! $KEEP; then
      psql -q -d postgres -c "DROP DATABASE IF EXISTS \"$temp_db\";" 2>/dev/null || true
    fi
    return 1
  fi
  ok "Init script applied"

  # 3. Seed reference data
  if [ "$name" = "nexus" ]; then
    log "Seeding reference data ..."
    for table in Planets SkillCategories Skills ProfessionCategories Professions ProfessionSkills; do
      seed_reference_data "$prod_db" "$temp_db" "$table" || true
    done
  fi

  # 4. Apply migrations (lenient)
  local migration_count=0
  log "Applying migrations ..."
  while IFS= read -r migration; do
    migration_count=$((migration_count + 1))
    apply_sql_lenient "$temp_db" "$migration" "$errlog"
  done < <(find "$migrations_dir" -maxdepth 1 -name '*.sql' -print0 | sort -zV | tr '\0' '\n')

  local total_errors
  total_errors=$(grep -ci 'FEHLER\|ERROR' "$errlog" 2>/dev/null || echo 0)
  log "Applied $migration_count migrations ($total_errors errors in log)"

  # 5. Structural comparison
  log "Comparing schema structure ..."
  local aspect_fails=0

  for aspect in tables columns types indexes constraints triggers functions sequences views; do
    if ! compare_aspect "$aspect" "$prod_db" "$temp_db" "$diff_file"; then
      aspect_fails=$((aspect_fails + 1))
    fi
  done

  if [ "$aspect_fails" -eq 0 ]; then
    ok "$name: all schema aspects match! (init + $migration_count migrations)"
    PASS_COUNT=$((PASS_COUNT + 1))
    rm -f "$diff_file" "$errlog"
  else
    fail "$name: $aspect_fails schema aspects differ"
    echo "    Full diff: $diff_file"
    echo "    Error log: $errlog"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi

  # 6. Cleanup
  if ! $KEEP; then
    log "Dropping $temp_db ..."
    psql -q -d postgres \
      -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$temp_db' AND pid <> pg_backend_pid();" \
      > /dev/null 2>&1 || true
    psql -q -d postgres -c "DROP DATABASE IF EXISTS \"$temp_db\";" 2>/dev/null || true
  else
    log "Keeping $temp_db for inspection"
  fi
}

# --- Main -------------------------------------------------------------------

echo "============================================"
echo "  Migration Validation Test"
echo "============================================"
echo "  Host: $PGHOST:$PGPORT  User: $PGUSER"
echo "============================================"

if $TEST_NEXUS; then
  test_database "nexus" \
    "$SCRIPT_DIR/nexus/000_init.sql" \
    "$SCRIPT_DIR/nexus/migrations" \
    "nexus"
fi

if $TEST_USERS; then
  test_database "nexus_users" \
    "$SCRIPT_DIR/nexus_users/000_init.sql" \
    "$SCRIPT_DIR/nexus_users/migrations" \
    "nexus_users"
fi

# --- Summary ----------------------------------------------------------------

echo ""
echo "============================================"
echo "  Results: $PASS_COUNT passed, $FAIL_COUNT failed"
echo "============================================"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
exit 0
