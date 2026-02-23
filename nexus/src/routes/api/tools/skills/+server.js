//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireGrantAPI } from '$lib/server/auth.js';
import {
  getUserSkills,
  upsertUserSkills,
  createSkillImport,
  checkSkillImportRateLimit
} from '$lib/server/skillsDb.js';

const MAX_SKILLS = 200;
const MAX_SKILL_NAME_LENGTH = 100;

function sanitizeSkills(skills) {
  if (typeof skills !== 'object' || skills === null || Array.isArray(skills)) {
    return null;
  }

  const sanitized = {};
  let count = 0;

  for (const [name, value] of Object.entries(skills)) {
    if (count >= MAX_SKILLS) break;
    if (typeof name !== 'string' || name.length > MAX_SKILL_NAME_LENGTH) continue;
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) continue;

    sanitized[name] = Math.round(value * 10000) / 10000; // 4 decimal precision
    count++;
  }

  return sanitized;
}

export async function GET({ locals }) {
  const user = requireGrantAPI(locals, 'skills.read');

  try {
    const result = await getUserSkills(user.id);
    if (!result) return getResponse({ skills: {}, updated_at: null }, 200);
    return getResponse(result, 200);
  } catch (error) {
    console.error('Error fetching user skills:', error);
    return getResponse({ error: 'Failed to fetch skills.' }, 500);
  }
}

export async function PUT({ request, locals }) {
  const user = requireGrantAPI(locals, 'skills.manage');

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON.' }, 400);
  }

  const skills = sanitizeSkills(body.skills);
  if (!skills) {
    return getResponse({ error: 'Invalid skills data.' }, 400);
  }

  try {
    // Check if this is an import (track history) or just a save
    if (body.trackImport !== false) {
      const rateCheck = await checkSkillImportRateLimit(user.id);
      if (!rateCheck.allowed) {
        return getResponse({ error: rateCheck.reason }, 429);
      }

      const existing = await getUserSkills(user.id);
      const oldSkills = existing?.skills || {};
      const importResult = await createSkillImport(user.id, oldSkills, skills);

      return getResponse({
        skills,
        import: importResult
      }, 200);
    }

    // Simple save without tracking
    await upsertUserSkills(user.id, skills);
    return getResponse({ skills }, 200);

  } catch (error) {
    console.error('Error saving user skills:', error);
    return getResponse({ error: 'Failed to save skills.' }, 500);
  }
}
