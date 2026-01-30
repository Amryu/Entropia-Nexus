//@ts-nocheck
import { getUserServices } from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

// GET user's own services
export async function GET({ locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  try {
    const services = await getUserServices(user.id);
    return getResponse(services, 200);
  } catch (error) {
    console.error('Error fetching user services:', error);
    return getResponse({ error: 'Failed to fetch services.' }, 500);
  }
}
