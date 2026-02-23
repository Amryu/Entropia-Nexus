//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireGrantAPI } from '$lib/server/auth.js';
import { getSkillImports } from '$lib/server/skillsDb.js';

export async function GET({ url, locals }) {
  const user = requireGrantAPI(locals, 'skills.read');

  const limit = Math.min(Math.max(parseInt(url.searchParams.get('limit'), 10) || 20, 1), 100);
  const offset = Math.max(parseInt(url.searchParams.get('offset'), 10) || 0, 0);

  try {
    const imports = await getSkillImports(user.id, limit, offset);
    return getResponse(imports, 200);
  } catch (error) {
    console.error('Error fetching skill imports:', error);
    return getResponse({ error: 'Failed to fetch import history.' }, 500);
  }
}
