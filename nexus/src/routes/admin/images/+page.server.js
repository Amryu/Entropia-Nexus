// @ts-nocheck
import { getPendingImages, getApprovedImages, approveImage, denyImage, deleteApprovedImage } from '$lib/server/imageProcessor.js';
import { fail } from '@sveltejs/kit';

export async function load() {
  const [pendingImages, approvedImages] = await Promise.all([
    getPendingImages(),
    getApprovedImages()
  ]);

  return {
    pendingImages,
    approvedImages
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
