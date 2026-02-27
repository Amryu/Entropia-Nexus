//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireGrantAPI } from '$lib/server/auth.js';
import { getSkillHistory } from '$lib/server/skillsDb.js';

export async function GET({ url, locals }) {
  const user = requireGrantAPI(locals, 'skills.read');

  const skills = url.searchParams.getAll('skill');
  const from = url.searchParams.get('from');
  const to = url.searchParams.get('to');

  // Validate date params
  if (from && isNaN(Date.parse(from))) {
    return getResponse({ error: 'Invalid "from" date.' }, 400);
  }
  if (to && isNaN(Date.parse(to))) {
    return getResponse({ error: 'Invalid "to" date.' }, 400);
  }

  try {
    const history = await getSkillHistory(user.id, {
      skills: skills.length > 0 ? skills : null,
      from: from || null,
      to: to || null,
    });
    return getResponse(history, 200);
  } catch (error) {
    console.error('Error fetching skill history:', error);
    return getResponse({ error: 'Failed to fetch skill history.' }, 500);
  }
}
