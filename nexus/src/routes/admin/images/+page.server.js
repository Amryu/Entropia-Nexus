// @ts-nocheck
import { getPendingImages, getApprovedImages, approveImage, denyImage, deleteApprovedImage } from '$lib/server/imageProcessor.js';
import { fail } from '@sveltejs/kit';
import { pool } from '$lib/server/db.js';

// API base URL for fetching entity data
const API_BASE = process.env.INTERNAL_API_URL || 'http://api:3000';

// Entity type to API endpoint mapping
const TYPE_ENDPOINT_MAP = {
  'weapon': '/weapons',
  'mob': '/mobs',
  'armorset': '/armorsets',
  'material': '/materials',
  'blueprint': '/blueprints',
  'skill': '/skills',
  'profession': '/professions',
  'vendor': '/vendors',
  'clothing': '/clothings',
  'consumable': '/stimulants',
  'capsule': '/capsules',
  'medicaltool': '/medicaltools',
  'medicalchip': '/medicalchips',
  'vehicle': '/vehicles',
  'pet': '/pets',
  'strongbox': '/strongboxes',
  'shop': '/shops',
  'location': '/locations',
  // Tools subtypes
  'refiner': '/refiners',
  'scanner': '/scanners',
  'finder': '/finders',
  'excavator': '/excavators',
  'teleportationchip': '/teleportationchips',
  'effectchip': '/effectchips',
  'misctool': '/misctools',
  // Attachment subtypes
  'weaponamplifier': '/weaponamplifiers',
  'weaponvisionattachment': '/weaponvisionattachments',
  'absorber': '/absorbers',
  'armorplating': '/armorplatings',
  'finderamplifier': '/finderamplifiers',
  'enhancer': '/enhancers',
  'mindforceimplant': '/mindforceimplants',
  // Furnishing subtypes
  'furniture': '/furniture',
  'decoration': '/decorations',
  'storagecontainer': '/storagecontainers',
  'sign': '/signs'
};

// Get entity name by type and ID via API call
async function getEntityName(entityType, entityId) {
  const endpoint = TYPE_ENDPOINT_MAP[entityType.toLowerCase()];
  if (!endpoint) {
    return null;
  }

  try {
    const response = await fetch(`${API_BASE}${endpoint}/${entityId}`);
    if (!response.ok) {
      return null;
    }
    const data = await response.json();
    return data?.Name || data?.Properties?.Name || null;
  } catch (err) {
    console.error(`Failed to get entity name for ${entityType}/${entityId}:`, err);
    return null;
  }
}

// Get uploader info by ID
async function getUploaderInfo(uploaderId) {
  if (!uploaderId) return null;

  try {
    const result = await pool.query(
      `SELECT id, eu_name, global_name, username
       FROM users
       WHERE id = $1
       LIMIT 1`,
      [uploaderId]
    );
    const user = result.rows[0];
    if (!user) return null;
    const displayName = user.eu_name || user.global_name || user.username || String(user.id);
    const profileName = user.eu_name || String(user.id);
    return { displayName, profileName };
  } catch (err) {
    console.error(`Failed to get uploader name for ${uploaderId}:`, err);
    return null;
  }
}

export async function load() {
  const [pendingImages, approvedImages] = await Promise.all([
    getPendingImages(),
    getApprovedImages()
  ]);

  // Enrich pending images with entity names and uploader names
  const enrichedPending = await Promise.all(
    pendingImages.map(async (image) => {
      const [entityName, uploaderInfo] = await Promise.all([
        getEntityName(image.entityType, image.entityId),
        getUploaderInfo(image.uploaderId)
      ]);
      return {
        ...image,
        entityName: entityName || image.entityId,
        uploaderName: uploaderInfo?.displayName || 'Unknown',
        uploaderProfile: uploaderInfo?.profileName || null
      };
    })
  );

  // Enrich approved images with entity names
  const enrichedApproved = await Promise.all(
    approvedImages.map(async (image) => {
      const entityName = await getEntityName(image.entityType, image.entityId);
      return {
        ...image,
        entityName: entityName || image.entityId
      };
    })
  );

  return {
    pendingImages: enrichedPending,
    approvedImages: enrichedApproved
  };
}

export const actions = {
  approve: async ({ request }) => {
    const formData = await request.formData();
    const entityType = formData.get('entityType');
    const entityId = formData.get('entityId');

    if (!entityType || !entityId) {
      return fail(400, { error: 'Entity type and ID are required' });
    }

    try {
      await approveImage(entityType, entityId);
      return { success: true, action: 'approved' };
    } catch (error) {
      return fail(500, { error: error.message || 'Failed to approve image' });
    }
  },

  deny: async ({ request }) => {
    const formData = await request.formData();
    const entityType = formData.get('entityType');
    const entityId = formData.get('entityId');

    if (!entityType || !entityId) {
      return fail(400, { error: 'Entity type and ID are required' });
    }

    try {
      await denyImage(entityType, entityId);
      return { success: true, action: 'denied' };
    } catch (error) {
      return fail(500, { error: error.message || 'Failed to deny image' });
    }
  },

  delete: async ({ request }) => {
    const formData = await request.formData();
    const entityType = formData.get('entityType');
    const entityId = formData.get('entityId');

    if (!entityType || !entityId) {
      return fail(400, { error: 'Entity type and ID are required' });
    }

    try {
      await deleteApprovedImage(entityType, entityId);
      return { success: true, action: 'deleted' };
    } catch (error) {
      return fail(500, { error: error.message || 'Failed to delete image' });
    }
  }
};
