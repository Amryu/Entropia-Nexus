# Admin Dashboard

## Overview

The admin dashboard provides administrators with tools to:
1. Monitor and manage entity changes (items, mobs, vendors, etc.)
2. Manage users (lock, ban, view metrics)
3. View platform statistics and user activity

## Change Process Documentation

### Entity Types

Changes can be submitted for the following entity types:
- **Items**: Weapon, ArmorSet, MedicalTool, MedicalChip, Refiner, Scanner, Finder, Excavator, TeleportChip, EffectChip, MiscTool, WeaponAmplifier, WeaponVisionAttachment, Absorber, FinderAmplifier, ArmorPlating, MindforceImplant, Blueprint, Material, Pet, Consumable, CreatureControlCapsule, Vehicle, Furniture, Decoration, StorageContainer, Sign, Clothing
- **Information**: Mob, Vendor, RefiningRecipe
- **Market**: Shop

### Change States

| State | Description |
|-------|-------------|
| Draft | Saved locally, not yet submitted for review |
| Pending | Submitted for moderator review (Discord thread created) |
| Approved | Moderator approved - changes applied to database |
| Denied | Moderator rejected the change |
| Deleted | Soft-deleted by user |

### Change Types

| Type | Description |
|------|-------------|
| Create | Creating a new entity |
| Update | Modifying an existing entity |
| Delete | Removing an entity (not commonly used) |

### Workflow

```
User edits entity
        ↓
    [Save as Draft] → Draft state (can continue editing)
        ↓
    [Ready for Review] → Pending state
        ↓
    Discord thread created automatically
        ↓
    Moderator reviews in Discord
        ↓
    ├── /approve → Approved (changes applied to DB)
    └── /deny → Denied (no changes made)
```

### Database Schema

#### changes table (nexus-users database)
```sql
id              integer PRIMARY KEY
author_id       bigint NOT NULL (FK to users)
type            change_type NOT NULL (Create/Update/Delete)
data            jsonb (full entity data as JSON)
state           change_state DEFAULT 'Draft'
entity          change_entity (entity type)
thread_id       bigint (Discord thread ID)
last_update     timestamp with time zone
created_at      timestamp with time zone (when change was first created)
reviewed_at     timestamp with time zone (when approved/denied)
reviewed_by     bigint (FK to users - admin who reviewed)
```

### Key Files

**Frontend:**
- `nexus/src/routes/api/changes/[[slug]]/+server.js` - Changes API
- `nexus/src/lib/components/EditForm.svelte` - Change submission form
- `nexus/src/lib/editConfigUtil.js` - Entity edit configurations

**Discord Bot:**
- `nexus-bot/commands/changes/approve.js` - Approval command
- `nexus-bot/commands/changes/deny.js` - Denial command
- `nexus-bot/changes/util.js` - Apply changes to database
- `nexus-bot/changes/entity.js` - Entity upsert configurations
- `nexus-bot/change.js` - Change validation and comparison

**Database:**
- `nexus/src/lib/server/db.js` - Database functions

## User Management

### User States

| State | Description | Effect |
|-------|-------------|--------|
| Normal | Default state | Full access based on verification |
| Locked | Restricted access | Cannot interact with verified-only features |
| Banned | Complete access denial | Cannot log in, sessions expired, Discord ban |

### Lock vs Ban

**Lock:**
- User can still log in and view content
- Cannot perform actions requiring verified status
- Typically used for temporary issues or warnings
- No duration limit (manual unlock required)

**Ban:**
- User cannot log in at all
- All sessions immediately expired
- Optional duration (can be permanent)
- Discord bot automatically bans from server
- Admins can still impersonate for investigation

### Database Fields (users table)

```sql
locked          boolean DEFAULT false
locked_at       timestamp with time zone
locked_reason   text
locked_by       bigint (FK to users - admin who locked)

banned          boolean DEFAULT false
banned_at       timestamp with time zone
banned_until    timestamp with time zone (NULL = permanent)
banned_reason   text
banned_by       bigint (FK to users - admin who banned)
```

## Admin Routes

| Route | Description |
|-------|-------------|
| /admin | Dashboard overview |
| /admin/changes | Change monitoring |
| /admin/changes/[id] | Individual change detail |
| /admin/users | User management |
| /admin/users/[id] | User detail and metrics |

## UI Components

### Admin Layout (`/admin/+layout.svelte`)

The admin panel uses a sidebar navigation layout:

**Desktop:**
- Fixed 220px sidebar with navigation items
- Dashboard, Changes, Users links

**Mobile (≤ 768px):**
- Sidebar hidden by default (off-screen left)
- Floating toggle button (bottom-left corner)
- Overlay backdrop when sidebar is open
- Sidebar slides in from left on toggle
- Closes automatically when clicking overlay or navigation link

### User Management Table

The `/admin/users` page uses `FancyTable.svelte` for the user list:

**Features:**
- Virtual scrolling (renders only visible rows)
- Lazy loading (fetches 50 users at a time as user scrolls)
- Reactive sorting by Discord Name or EU Name (no page reload)
- Column-based filtering (Discord Name, EU Name columns)
- Status filter dropdown (All, Admins, Verified, Unverified, Locked, Banned)
- Click row to navigate to user detail page

**Custom Cell Formatters:**
- Avatar + name combination in Discord Name column
- Status badges (Banned, Locked, Admin, Verified, Unverified)
- Verified checkmark indicator

## Permissions

All admin routes require:
- User must be logged in
- User must have `administrator = true`
- When impersonating, real user must be admin (use realUser for checks)
