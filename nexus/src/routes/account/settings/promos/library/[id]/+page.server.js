// @ts-nocheck
import { error } from '@sveltejs/kit';
import { requireVerified } from '$lib/server/auth.js';
import { getPromoById, getPromoImages } from '$lib/server/db.js';

export async function load({ locals, params }) {
  const user = requireVerified(locals);

  const { id } = params;

  // "new" = create mode
  if (id === 'new') {
    return { promo: null, images: [], isNew: true };
  }

  const promoId = parseInt(id);
  if (isNaN(promoId)) {
    throw error(400, 'Invalid promo ID');
  }

  const promo = await getPromoById(promoId);
  if (!promo) {
    throw error(404, 'Promo not found');
  }

  if (String(promo.owner_id) !== String(user.id)) {
    throw error(403, 'You can only edit your own promos');
  }

  const images = await getPromoImages(promoId);

  return {
    promo: {
      id: promo.id,
      name: promo.name,
      promo_type: promo.promo_type,
      title: promo.title,
      summary: promo.summary,
      link: promo.link,
      content_html: promo.content_html,
      created_at: promo.created_at?.toISOString?.() ?? promo.created_at,
      updated_at: promo.updated_at?.toISOString?.() ?? promo.updated_at
    },
    images: images.map(img => ({
      slot_variant: img.slot_variant,
      image_path: img.image_path,
      width: img.width,
      height: img.height
    })),
    isNew: false
  };
}
