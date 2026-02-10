// @ts-nocheck
import { getResponse, apiCall } from '$lib/util.js';
import {
  getUserProfileById,
  getUserProfileByEntropiaName,
  getUserContributionStats,
  getUserServices,
  getUserPublicLoadouts,
  getLoadoutByShareCode,
  updateUserProfile,
  getSocietyById,
  getPendingSocietyJoinRequest
} from '$lib/server/db.js';
import { pool } from '$lib/server/db.js';
import { getUserPublicOrders } from '$lib/server/trade-requests.js';
import { sanitizeRichText } from '$lib/server/sanitizeRichText.js';
import { getApprovedImagePath } from '$lib/server/imageProcessor.js';

const RANK_CACHE_TTL = 15 * 60 * 1000;
const rankCache = {
  allTime: { expiresAt: 0, data: new Map() },
  monthly: { expiresAt: 0, data: new Map() }
};

async function getRankMap(scope) {
  const cache = rankCache[scope];
  const now = Date.now();
  if (cache && cache.expiresAt > now && cache.data.size > 0) {
    return cache.data;
  }

  const isMonthly = scope === 'monthly';
  const query = `
    WITH counts AS (
      SELECT
        u.id as user_id,
        COALESCE(
          COUNT(c.id) FILTER (
            WHERE c.state = 'Approved'
            ${isMonthly ? "AND c.last_update >= date_trunc('month', now()) AND c.last_update < (date_trunc('month', now()) + interval '1 month')" : ''}
          ),
          0
        ) as score
      FROM users u
      LEFT JOIN changes c ON c.author_id = u.id
      GROUP BY u.id
    )
    SELECT
      user_id,
      score,
      DENSE_RANK() OVER (ORDER BY score DESC) as rank
    FROM counts
  `;

  const { rows } = await pool.query(query);
  const map = new Map();
  rows.forEach(row => {
    map.set(String(row.user_id), {
      score: Number(row.score) || 0,
      rank: Number(row.rank) || 0
    });
  });

  rankCache[scope] = {
    expiresAt: now + RANK_CACHE_TTL,
    data: map
  };

  return map;
}

function resolveDiscordName(user) {
  if (!user) return '';
  if (String(user.discriminator) === '0') {
    return user.global_name || user.username || '';
  }
  if (user.username && user.discriminator != null) {
    return `${user.username}#${user.discriminator}`;
  }
  return user.global_name || user.username || '';
}

function resolveDiscordAvatar(user) {
  if (!user) return null;
  if (user.avatar) {
    return `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png`;
  }
  return `https://cdn.discordapp.com/embed/avatars/${Number(user.id) % 5}.png`;
}

async function getUserShopsFromApi(fetch, userId) {
  const encodedId = encodeURIComponent(String(userId));
  let shops = await apiCall(fetch, `/shops?OwnerId=${encodedId}`);
  if (!shops) {
    const allShops = await apiCall(fetch, `/shops`);
    shops = Array.isArray(allShops)
      ? allShops.filter(shop => String(shop?.OwnerId) === String(userId))
      : [];
  }

  if (!Array.isArray(shops)) return [];

  return shops.map(shop => ({
    id: shop.Id ?? shop.id,
    name: shop.Name ?? shop.name,
    planet_name: shop.Planet?.Name ?? shop.Planet?.name ?? null
  })).filter(shop => shop.id != null);
}

/** @type {import('./$types').RequestHandler} */
export async function GET({ params, locals, fetch }) {
  const identifier = params.identifier;
  if (!identifier) {
    return getResponse({ error: 'User identifier required.' }, 400);
  }

  const isNumeric = /^\d+$/.test(identifier);
  const decodedName = decodeURIComponent(identifier).replace(/~/g, ' ');

  let profileUser = null;
  if (isNumeric) {
    profileUser = await getUserProfileById(identifier);
  } else {
    profileUser = await getUserProfileByEntropiaName(decodedName);
  }

  if (!profileUser) {
    return getResponse({ error: 'User not found.' }, 404);
  }

  const sessionUser = locals.session?.user;
  const sessionUserId = sessionUser ? String(sessionUser.Id || sessionUser.id) : null;
  const isOwner = sessionUserId && String(profileUser.id) === sessionUserId;

  const [scores, services, shops, marketOffers] = await Promise.all([
    getUserContributionStats(profileUser.id),
    getUserServices(profileUser.id),
    getUserShopsFromApi(fetch, profileUser.id),
    getUserPublicOrders(profileUser.id)
  ]);

  const [allTimeRanks, monthlyRanks] = await Promise.all([
    getRankMap('allTime'),
    getRankMap('monthly')
  ]);

  const allTimeRank = allTimeRanks.get(String(profileUser.id)) || { score: scores.total, rank: 0 };
  const monthlyRank = monthlyRanks.get(String(profileUser.id)) || { score: scores.monthly, rank: 0 };

  const discordAvatarUrl = resolveDiscordAvatar(profileUser);
  const hasCustomImage = !!getApprovedImagePath('user', profileUser.id, 'icon');
  const profileImageUrl = hasCustomImage ? `/api/image/user/${profileUser.id}` : null;

  const society = profileUser.society_id && profileUser.society_id > 0
    ? await getSocietyById(profileUser.society_id)
    : null;

  const pendingSocietyRequest = profileUser.society_id === -1
    ? await getPendingSocietyJoinRequest(profileUser.id)
    : null;

  const pendingSociety = !society && pendingSocietyRequest
    ? await getSocietyById(pendingSocietyRequest.society_id)
    : null;

  const showcaseLoadout = profileUser.showcase_loadout_code
    ? await getLoadoutByShareCode(profileUser.showcase_loadout_code)
    : null;

  const publicLoadouts = isOwner ? await getUserPublicLoadouts(profileUser.id) : [];

  return getResponse({
    profile: {
      id: profileUser.id,
      euName: profileUser.eu_name,
      discordName: resolveDiscordName(profileUser),
      discordAvatarUrl,
      profileImageUrl,
      hasCustomImage,
      societyId: profileUser.society_id ?? null,
      society: society || pendingSociety,
      pendingSocietyRequest,
      biographyHtml: profileUser.biography_html || '',
      defaultTab: profileUser.default_profile_tab || 'General',
      showcaseLoadoutCode: profileUser.showcase_loadout_code || null
    },
    scores: {
      total: scores.total,
      monthly: scores.monthly,
      totalRank: allTimeRank.rank || 1,
      monthlyRank: monthlyRank.rank || 1
    },
    services: services || [],
    shops: shops || [],
    offers: marketOffers || [],
    avatar: {
      showcaseLoadout,
      publicLoadouts
    },
    permissions: {
      isOwner
    }
  }, 200);
}

/** @type {import('./$types').RequestHandler} */
export async function PATCH({ params, request, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  const identifier = params.identifier;
  if (!identifier) {
    return getResponse({ error: 'User identifier required.' }, 400);
  }

  const isNumeric = /^\d+$/.test(identifier);
  const decodedName = decodeURIComponent(identifier).replace(/~/g, ' ');
  const profileUser = isNumeric
    ? await getUserProfileById(identifier)
    : await getUserProfileByEntropiaName(decodedName);

  if (!profileUser) {
    return getResponse({ error: 'User not found.' }, 404);
  }

  const userId = String(user.Id || user.id);
  if (String(profileUser.id) !== userId && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You do not have permission to edit this profile.' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const next = {
    biography_html: body.biographyHtml != null
      ? sanitizeRichText(body.biographyHtml || '')
      : (profileUser.biography_html ?? null),
    default_profile_tab: body.defaultTab ?? profileUser.default_profile_tab ?? 'General',
    showcase_loadout_code: body.showcaseLoadoutCode ?? profileUser.showcase_loadout_code ?? null
  };

  if (next.default_profile_tab && !['General', 'Avatar', 'Services', 'Shops', 'Offers'].includes(next.default_profile_tab)) {
    return getResponse({ error: 'Invalid default tab.' }, 400);
  }

  const updated = await updateUserProfile(profileUser.id, next);

  return getResponse({
    success: true,
    profile: {
      id: updated.id,
      euName: updated.eu_name,
      societyId: updated.society_id ?? null,
      biographyHtml: updated.biography_html || '',
      defaultTab: updated.default_profile_tab || 'General',
      showcaseLoadoutCode: updated.showcase_loadout_code || null
    }
  }, 200);
}
