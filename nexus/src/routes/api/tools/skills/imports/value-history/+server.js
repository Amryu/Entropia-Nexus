//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getSkillValueHistory } from '$lib/server/skillsDb.js';

export async function GET({ locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'You must be logged in.' }, 401);

  try {
    const history = await getSkillValueHistory(user.id);
    return getResponse(history, 200);
  } catch (error) {
    console.error('Error fetching skill value history:', error);
    return getResponse({ error: 'Failed to fetch value history.' }, 500);
  }
}
