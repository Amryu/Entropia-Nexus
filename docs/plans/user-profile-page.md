# User Profile Page Plan

## Goal
Create a public user profile page at `/user/<EU name>` or `/user/<id>` that shows profile information, contributions, and owned content, with editable fields for the owner.

## Routing & Canonicalization
- Routes:
  - `/user/[id]` (numeric id)
  - `/user/[euName]` (URL‑encoded EU name)
- Resolution order:
  - If segment is numeric → treat as id.
  - Else treat as EU name (decode and lookup case‑insensitively).
- Canonical URL:
  - Prefer `/user/<EU name>` for public sharing.
  - If user is requested by id, redirect to name when available.

## Data Requirements
### Core profile fields
- `id`
- `euName`
- `discordName` (optional)
- `profileImageUrl` (optional, uploaded by user; max 320x320)
- `societyName` (editable)
- `biography` (editable rich text)
- `defaultTab` (editable enum: `general`, `avatar`, `services`, `shops`, `offers`)

### Contribution score
For now: `approvedChangeCount` = number of approved changes.
- Total score: `approvedChangeCount`
- Monthly score: count of approved changes within current calendar month
- Rank: computed by comparing scores across all users (monthly and all‑time)
  - Ties share the same rank number
  - Cache computed ranks for 15 minutes

### Related content
Show only when user has data:
- Services (with links)
- Shops (owned)
- Offers (if feature exists in the future)
- Avatar tab: show if user filled skill values and/or has at least one public loadout selected as “showcase”

## UI/UX Spec
### Header
- Profile picture
- EU name (primary)
- Discord name (secondary)
- Edit button (visible to owner only)
- Settings button (no functionality yet)
  - If no uploaded profile image, use Discord profile picture
  - Profile image can be changed in edit mode (upload max 320x320)

### Tabs
Order: `General`, `Avatar`, `Services`, `Shops`, `Offers`
- Only render tabs with data; always render `General`.
- If default tab is hidden (no data), fall back to first available tab.
- Owner can set default tab (applies when other players view profile).
- All tabs shown (besides offers for now) during edit mode

### General tab
- Contribution score:
  - Total
  - This month
  - Rank (derived)
- Biography (rich text)

### Edit mode
Owner can edit:
- Society name
- Biography (RichTextEdit)
- Default tab
- Skills & Showcase Loadout (save the share_code in database) - editable in respective tab
- Profile picture (upload max 320x320)

## Menu Integration
- Fix mobile menu profile link to new route.
- Add profile link to desktop menu bar (visible when logged in).

## API / Data Flow
- `GET /api/users/profile?name=<euName>` or `GET /api/users/profile/<id>`
  - Returns profile, contributions summary, and related content links.
- `PATCH /api/users/profile/<id>`
  - Accepts `societyName`, `biography`, `defaultTab`
  - Auth: owner or admin

## DB / Model Updates
- Add fields to user profile table:
  - `society_name` (string, nullable)
  - `biography` (rich text JSON or HTML)
  - `default_tab` (enum)
  - `profile_image_url` (optional if not already stored)
  - `profile_image_source` (enum: `upload` | `discord`) to track fallback choice
- Contribution stats may be derived via query, no new table required.

## ASCII Mockup
```
┌───────────────────────────────────────────────────────────────┐
│ [Photo]  EU Name                           [Edit Profile]     │
│         Discord#1234                                          │
│         Society: Example Society                              │
├───────────────────────────────────────────────────────────────┤
│ [ General ] [ Avatar ] [ Services ] [ Shops ] [ Offers ]      │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│ Contribution Score                                            │
│  - Total: 128 (#2)    - This Month: 12 (#5)                   │
│                                                               │
│ Biography                                                     │
│  (rich text content...)                                       │
│                                                               │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## Open Questions / Decisions
- Profile image storage and validation pipeline (local vs CDN, resizing).
  - local, use existing image upload endpoint with same restrictions. Images need approval as well.
- Biography storage format (HTML vs TipTap JSON).
  - HTML
- Which content types count as “Offers”.
  - Not yet implemented, leave as skeleton
- Avatar tab: define “showcase loadout” field and validation rules.
  - Use a Local Search Input that lets the user browse his PUBLIC loadouts. Save the share_code as identification


If the user has an image, replace their discord picture in the menu bar as well.