# Image Upload Workflow

Documentation for the entity image upload system with client-side cropping and admin approval.

## Overview

Entity images (icons) go through a staged upload process:
1. User selects and crops image client-side
2. Image is processed server-side and stored in pending
3. Admin reviews and approves/denies the image
4. Approved images are moved to public storage

**Auto-approve:** Some uploads skip the approval queue:
- `guide-category`, `announcement`, `item-set` — auto-approved by entity type
- `richtext` — auto-approved if the user has `wiki.approve` or `guide.edit` grants
- **Admin uploads** — any upload by a user with `admin.panel` grant is auto-approved

---

## Client-Side Components

### ImageUploader.svelte

**Location:** `nexus/src/lib/components/wiki/ImageUploader.svelte`

Main upload component with preview and crop integration.

#### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `currentImage` | `string\|null` | `null` | Current image URL |
| `entityType` | `string` | `''` | Entity type for API |
| `entityId` | `number\|string` | `''` | Entity ID for API |
| `editable` | `boolean` | `false` | Whether upload is enabled |
| `maxSizeMB` | `number` | `2` | Maximum file size in MB |

#### Events

| Event | Detail | Description |
|-------|--------|-------------|
| `upload` | `{ tempPath, previewUrl }` | Image uploaded successfully |

#### Usage

```svelte
<script>
  import ImageUploader from '$lib/components/wiki/ImageUploader.svelte';
  import { editMode } from '$lib/stores/wikiEditState.js';
</script>

<ImageUploader
  currentImage={entity.IconUrl}
  entityType="weapon"
  entityId={entity.Id}
  editable={$editMode}
  on:upload={(e) => {
    // Store temp path for submission with entity changes
    pendingImagePath = e.detail.tempPath;
  }}
/>
```

#### Features

- Drag and drop support
- File type validation (images only)
- File size validation (default 2MB max)
- Preview of current image
- Hover overlay for change action

---

### ImageCropper.svelte

**Location:** `nexus/src/lib/components/wiki/ImageCropper.svelte`

Square cropping interface using `svelte-easy-crop`.

#### Props

| Prop | Type | Description |
|------|------|-------------|
| `image` | `string` | Image data URL to crop |

#### Events

| Event | Description |
|-------|-------------|
| `confirm` | User clicked confirm |
| `cancel` | User clicked cancel |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `getCroppedImage()` | `Promise<Blob>` | Get cropped image as PNG blob |

#### Usage

Called internally by ImageUploader, but can be used standalone:

```svelte
<script>
  import ImageCropper from '$lib/components/wiki/ImageCropper.svelte';

  let cropperRef;

  async function handleConfirm() {
    const blob = await cropperRef.getCroppedImage();
    // Upload blob...
  }
</script>

<ImageCropper
  bind:this={cropperRef}
  image={imageDataUrl}
  on:confirm={handleConfirm}
  on:cancel={() => showCropper = false}
/>
```

#### Cropping Specs

- **Aspect Ratio:** 1:1 (square)
- **Output Size:** 512x512 pixels (icon), 128x128 pixels (thumbnail)
- **Output Format:** PNG blob

---

## Server-Side Processing

### Upload Endpoint

**Location:** `nexus/src/routes/api/uploads/entity-image/+server.js`

```
POST /api/uploads/entity-image
Content-Type: multipart/form-data

Form fields:
- image: File (the cropped image)
- entityType: string
- entityId: string
```

**Response:**
```json
{
  "tempPath": "/temp/weapon_123_abc123.png",
  "previewUrl": "/api/uploads/preview/weapon_123_abc123.png"
}
```

### Processing Pipeline

1. **Receive upload** - Validate file type and size
2. **Generate images** - Using `sharp` library:
   - Icon: 512x512 WebP
   - Thumbnail: 128x128 WebP
3. **Store in pending** - Save to pending directory with unique ID
4. **Create database record** - Track pending image for admin review
5. **Return temp path** - For preview and submission

### Image Processing (sharp)

```javascript
// nexus/src/lib/server/imageProcessor.js
import sharp from 'sharp';

export async function processEntityImage(buffer) {
  // Generate icon (512x512)
  const icon = await sharp(buffer)
    .resize(512, 512, { fit: 'cover' })
    .webp({ quality: 85 })
    .toBuffer();

  // Generate thumbnail (128x128)
  const thumb = await sharp(buffer)
    .resize(128, 128, { fit: 'cover' })
    .webp({ quality: 80 })
    .toBuffer();

  return { icon, thumb };
}
```

---

## Storage Structure

```
uploads/
├── temp/                       # Uploaded but not yet reviewed images
│   └── {uuid}/                 # Each upload gets a unique ID
│       ├── icon.webp           # 320x320 processed image
│       ├── thumb.webp          # 128x128 thumbnail
│       └── metadata.json       # Upload metadata (entityType, entityId, uploaderId, etc.)
├── pending/                    # Reserved for future workflow (submitted for approval)
│   └── {entity_type}/{entity_id}/
└── approved/                   # Approved images (publicly accessible)
    └── {entity_type}/{entity_id}/
        ├── icon.webp           # 320x320
        ├── thumb.webp          # 128x128
        └── metadata.json
```

---

## Docker Configuration

The uploads directory is configured as a Docker volume for persistent storage across container restarts and deployments.

### Environment Variable

```env
# Development: relative path is fine
UPLOAD_DIR=./uploads

# Production/Docker: absolute path to mounted volume
UPLOAD_DIR=/app/uploads
```

### docker-compose.yml

```yaml
volumes:
  nexus-uploads:

services:
  nexus:
    volumes:
      - type: volume
        source: nexus-uploads
        target: /app/uploads
    environment:
      - UPLOAD_DIR=/app/uploads
```

### Dockerfile

The Dockerfile includes:
- Dependencies for `sharp` library (vips-dev, fftw-dev)
- Creation of uploads directory with proper permissions
- Non-root user for security

```dockerfile
# Install dependencies for sharp (image processing)
RUN apk add --no-cache vips-dev fftw-dev build-base python3

# Create uploads directory with proper permissions
RUN mkdir -p /app/uploads/temp /app/uploads/pending /app/uploads/approved \
    && chown -R node:node /app/uploads

ENV UPLOAD_DIR=/app/uploads
USER node
```

### Backup Considerations

In production, the `nexus-uploads` Docker volume should be included in backup procedures:

```bash
# Backup volume
docker run --rm -v nexus-uploads:/data -v $(pwd):/backup alpine tar czf /backup/uploads-backup.tar.gz /data

# Restore volume
docker run --rm -v nexus-uploads:/data -v $(pwd):/backup alpine tar xzf /backup/uploads-backup.tar.gz -C /
```

### Nginx Configuration (if using reverse proxy)

```nginx
location /uploads/approved/ {
    alias /var/www/uploads/approved/;
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

Cloudflare handles additional edge caching.

---

## Admin Approval Workflow

### Pending Images List

**Location:** `nexus/src/routes/admin/images/+page.svelte`

Displays all pending images for review.

| Column | Description |
|--------|-------------|
| Preview | Thumbnail of pending image |
| Entity | Link to entity page |
| Type | Entity type |
| Uploaded | Upload timestamp |
| Uploader | User who uploaded |
| Actions | Approve / Deny buttons |

### Admin Endpoints

**List Pending:**
```
GET /api/admin/pending-images
Response: [{ id, entityType, entityId, uploadedBy, uploadedAt, previewUrl }]
```

**Approve Image:**
```
POST /api/admin/images/:id/approve
```
- Moves image from `pending/` to `approved/`
- Updates entity record with new image URL
- Notifies uploader (optional)

**Deny Image:**
```
POST /api/admin/images/:id/deny
Body: { reason: "Optional rejection reason" }
```
- Deletes image from `pending/`
- Notifies uploader with reason (optional)

---

## Integration with Entity Changes

Images are uploaded separately from entity data changes:

1. **Upload Flow (Independent)**
   - User uploads image during edit session
   - Image goes to pending queue immediately
   - Returns `tempPath` for preview

2. **Entity Change Flow**
   - User edits entity fields
   - Submits entity change (Draft → Pending → Approved)
   - Entity change does NOT include image data

3. **Approval Flow (Independent)**
   - Admin reviews entity change → Approves/Rejects
   - Admin reviews image separately → Approves/Rejects
   - Both can be approved independently

### Why Separate?

- Images require visual review (can't be auto-merged)
- Large binary data shouldn't be in change history
- Allows image-only updates without entity changes
- Simplifies change diffing (text only)

---

## Client-Side Implementation

### Full Upload Flow

```svelte
<script>
  import ImageUploader from '$lib/components/wiki/ImageUploader.svelte';
  import { editMode } from '$lib/stores/wikiEditState.js';
  import { createEventDispatcher } from 'svelte';

  export let entity;

  const dispatch = createEventDispatcher();

  let pendingImagePath = null;
  let previewUrl = null;

  function handleUpload(event) {
    pendingImagePath = event.detail.tempPath;
    previewUrl = event.detail.previewUrl;

    // Optionally notify parent
    dispatch('imageUploaded', { tempPath: pendingImagePath });
  }

  // Display logic: show preview if pending, else current image
  $: displayImage = previewUrl || entity?.IconUrl;
</script>

<div class="entity-image-section">
  <ImageUploader
    currentImage={displayImage}
    entityType="weapon"
    entityId={entity?.Id}
    editable={$editMode}
    on:upload={handleUpload}
  />

  {#if pendingImagePath}
    <span class="pending-badge">Image pending approval</span>
  {/if}
</div>
```

---

## Error Handling

### Client Errors

| Error | Message | Resolution |
|-------|---------|------------|
| Invalid type | "Please select an image file" | Select .jpg, .png, .gif, .webp |
| Too large | "Image must be smaller than 2MB" | Compress or resize image |
| Upload failed | "Upload failed" | Check network, retry |
| Crop failed | "Failed to crop image" | Try different image |

### Server Errors

| Status | Error | Cause |
|--------|-------|-------|
| 400 | "Missing image file" | No file in request |
| 400 | "Invalid entity type" | Unknown entity type |
| 401 | "Unauthorized" | Not logged in |
| 413 | "File too large" | Exceeded server limit |
| 415 | "Unsupported media type" | Not an image |
| 500 | "Processing failed" | sharp error |

---

## Security Considerations

### Validation

- **Client-side:** File type, size, dimensions
- **Server-side:** MIME type, file header, size limits
- **Processing:** Re-encode through sharp (strips metadata, validates format)

### Access Control

- Only authenticated users can upload
- Pending images not publicly accessible
- Admin-only approval endpoints
- Rate limiting on uploads

### Content Security

- Images re-encoded (no embedded scripts)
- Served with `Content-Type: image/webp`
- No user-controlled filenames in URLs

---

## Cleanup Jobs

### Temp Directory Cleanup

Scheduled job removes files older than 24 hours from `/temp/`:

```javascript
// Run daily via cron
async function cleanupTempUploads() {
  const tempDir = '/var/www/uploads/temp';
  const maxAge = 24 * 60 * 60 * 1000; // 24 hours
  const now = Date.now();

  const files = await fs.readdir(tempDir);
  for (const file of files) {
    const stat = await fs.stat(path.join(tempDir, file));
    if (now - stat.mtimeMs > maxAge) {
      await fs.unlink(path.join(tempDir, file));
    }
  }
}
```

### Pending Image Expiry

Optional: Auto-deny pending images older than 30 days.

---

## Testing

### Manual Testing

1. Navigate to entity page, enter edit mode
2. Click image upload area
3. Select image, verify cropper appears
4. Adjust crop, click confirm
5. Verify upload spinner, then preview
6. Submit entity changes
7. Check admin panel for pending image
8. Approve image, verify it appears on entity

### Playwright Testing

```javascript
test('can upload entity image', async ({ verifiedUser }) => {
  await verifiedUser.goto('/items/weapons/armatrix-ln-35');
  await verifiedUser.getByRole('button', { name: 'Edit' }).click();

  // Upload image
  const fileInput = await verifiedUser.locator('input[type="file"]');
  await fileInput.setInputFiles('tests/fixtures/test-image.png');

  // Wait for cropper
  await expect(verifiedUser.getByText('Crop Image')).toBeVisible();

  // Confirm crop
  await verifiedUser.getByRole('button', { name: 'Confirm' }).click();

  // Verify pending badge
  await expect(verifiedUser.getByText('Image pending approval')).toBeVisible();
});
```

---

## Related Documentation

- [wiki-components.md](wiki-components.md) - Component architecture
- [wiki-editing.md](wiki-editing.md) - WYSIWYG editing system
- [ui-styling.md](ui-styling.md) - CSS styling patterns
