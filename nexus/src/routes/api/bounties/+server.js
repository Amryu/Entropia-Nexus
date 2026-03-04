// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getActiveRewardRules, getTopContributors } from '$lib/server/db';

export async function GET() {
  try {
    const [rules, contributors] = await Promise.all([
      getActiveRewardRules(),
      getTopContributors(10)
    ]);

    // Group rules by category
    const categories = {};
    for (const rule of rules) {
      const cat = rule.category || 'Other';
      if (!categories[cat]) categories[cat] = [];
      categories[cat].push({
        id: rule.id,
        name: rule.name,
        description: rule.description,
        entities: rule.entities,
        change_type: rule.change_type,
        min_amount: rule.min_amount,
        max_amount: rule.max_amount,
        contribution_score: rule.contribution_score
      });
    }

    return json({
      categories,
      contributors: contributors.map(c => ({
        id: String(c.id),
        global_name: c.global_name,
        eu_name: c.eu_name,
        avatar: c.avatar,
        approved_count: parseInt(c.approved_count)
      }))
    });
  } catch {
    return json({ categories: {}, contributors: [] });
  }
}
