// @ts-nocheck
import { apiCall } from '$lib/util';

export async function load({ fetch }) {
  const [skills, professions] = await Promise.all([
    apiCall(fetch, '/skills'),
    apiCall(fetch, '/professions')
  ]);

  // Normalize profession data: ensure each profession has a flat Skills array
  const normalizedProfessions = (professions || []).map(p => ({
    Name: p.Name,
    Category: p.Category?.Name || p.Category || null,
    Skills: (p.Skills || []).map(s => ({
      Name: s.Skill?.Name || s.Name,
      Weight: s.Weight ?? 0
    })),
    Unlocks: p.Unlocks || []
  }));

  // Normalize skill data
  const normalizedSkills = (skills || []).map(s => ({
    Name: s.Name,
    Category: s.Category?.Name || s.Category || null,
    HPIncrease: s.Properties?.HpIncrease ?? s.HPIncrease ?? null,
    IsExtractable: s.Properties?.IsExtractable ?? s.IsExtractable ?? true,
    IsHidden: s.Properties?.IsHidden ?? (s.Hidden === 1) ?? false,
    Professions: (s.Professions || []).map(p => ({
      Name: p.Profession?.Name || p.Name,
      Weight: p.Weight ?? 0
    })),
    Unlocks: (s.Unlocks || []).map(u => ({
      Level: u.Level ?? 0,
      Profession: u.Profession?.Name || u.Name || null
    }))
  }));

  return {
    skillsMetadata: normalizedSkills,
    professionsMetadata: normalizedProfessions
  };
}
