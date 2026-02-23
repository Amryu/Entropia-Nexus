//@ts-nocheck
import { getUserServices } from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";
import { requireGrantAPI } from '$lib/server/auth.js';

// GET user's own services
export async function GET({ locals }) {
  const user = requireGrantAPI(locals, 'services.manage');

  try {
    const services = await getUserServices(user.id);
    return getResponse(services, 200);
  } catch (error) {
    console.error('Error fetching user services:', error);
    return getResponse({ error: 'Failed to fetch services.' }, 500);
  }
}
