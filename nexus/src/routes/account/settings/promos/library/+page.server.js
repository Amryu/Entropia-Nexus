// @ts-nocheck
import { requireVerified } from '$lib/server/auth.js';
import { getPromosByOwner } from '$lib/server/db.js';

export async function load({ locals }) {
  const user = requireVerified(locals);

  const promos = await getPromosByOwner(user.id);

  return {
    promos: promos.map(p => ({
      id: p.id,
      name: p.name,
      promo_type: p.promo_type,
      title: p.title,
      summary: p.summary,
      link: p.link,
      created_at: p.created_at?.toISOString?.() ?? p.created_at,
      updated_at: p.updated_at?.toISOString?.() ?? p.updated_at
    }))
  };
}
