const fs = require('fs');

// Read the input data
const data = JSON.parse(fs.readFileSync('tools/data import/missions/mission-analysis-input.json', 'utf8'));
const missions = data.missions.slice(1000, 1200);
const mobNamesList = data.mobNames;
const skillNamesList = data.skillNames;

console.log(`Processing ${missions.length} missions...`);

// Helper function to find matching mob names
function extractMobNames(objective, missionName, mobList) {
  if (!objective || objective.trim() === '') return [];

  const obj = objective.toLowerCase();
  const results = [];

  // Try to find mob names in the objective
  for (const mob of mobList) {
    const mobLower = mob.toLowerCase();
    if (obj.includes(mobLower)) {
      results.push(mob);
    }
  }

  return results;
}

// Helper function to extract count
function extractCount(objective, missionName) {
  if (!objective) return null;

  // Look for patterns like "Kill 500", "Hunt 100", "Mine 50"
  const countMatch = objective.match(/(?:kill|hunt|mine|earn|find)\s+(\d+)/i);
  if (countMatch) return parseInt(countMatch[1]);

  // Look for "worth X points" pattern
  const pointsMatch = objective.match(/worth\s+(\d+)\s+points/i);
  if (pointsMatch) return parseInt(pointsMatch[1]);

  // Try to extract from mission name
  const nameMatch = missionName.match(/-\s*(\d+)/);
  if (nameMatch) return parseInt(nameMatch[1]);

  return null;
}

// Helper function to parse reward text
function parseRewards(rewardText, skillList) {
  const items = [];
  const skills = [];

  if (!rewardText || rewardText.trim() === '') {
    return { items, skills, isChoice: false };
  }

  // Check if it's a choice reward
  const hasChoiceSeparator = / or | \/ /.test(rewardText);

  // Split by separators
  const parts = rewardText.split(/\s*(?:\/|\bor\b)\s*/i);

  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed) continue;

    // Check if this part is a skill
    let isSkill = false;
    for (const skill of skillList) {
      const skillLower = skill.toLowerCase();
      if (trimmed.toLowerCase().includes(skillLower)) {
        isSkill = true;
        // Extract PED value
        const pedMatch = trimmed.match(/\(([0-9.]+)\s*PED/i);
        const pedValue = pedMatch ? parseFloat(pedMatch[1]) : null;
        skills.push({ name: skill, pedValue: pedValue });
        break;
      }
    }

    if (!isSkill && trimmed) {
      // It's an item - try to extract quantity
      const qtyMatch = trimmed.match(/^(\d+)\s+(.+?)$/);
      if (qtyMatch) {
        items.push({ name: qtyMatch[2], quantity: parseInt(qtyMatch[1]) });
      } else {
        items.push({ name: trimmed, quantity: 1 });
      }
    }
  }

  return { items, skills, isChoice: hasChoiceSeparator && parts.length > 1 };
}

const result = {};

for (const mission of missions) {
  const missionName = mission.name;
  const objective = mission.objective || '';
  const type = (mission.type || '').toLowerCase();

  let objectiveType = null;
  let payload = {};
  let stepDescription = '';

  // Determine objective type
  if (type === 'hunting' || objective.toLowerCase().includes('kill') || objective.toLowerCase().includes('hunt')) {
    const mobs = extractMobNames(objective, missionName, mobNamesList);
    const count = extractCount(objective, missionName);

    objectiveType = 'KillCount';
    payload = { mobs: mobs.length > 0 ? mobs : [] };
    if (count !== null) payload.totalCountRequired = count;

    if (count && mobs.length > 0) {
      stepDescription = `Kill ${count} ${mobs[0]}`;
    } else if (count) {
      stepDescription = `Kill ${count}`;
    } else if (mobs.length > 0) {
      stepDescription = `Kill ${mobs[0]}`;
    } else {
      stepDescription = 'Kill creatures';
    }
  } else if (objective.toLowerCase().includes('craft') && objective.toLowerCase().includes('success')) {
    objectiveType = 'CraftSuccess';
    const count = extractCount(objective, missionName);
    if (count !== null) payload.totalCountRequired = count;
    stepDescription = count ? `Craft ${count} items successfully` : 'Craft items successfully';
  } else if (objective.toLowerCase().includes('craft')) {
    objectiveType = 'CraftAttempt';
    const count = extractCount(objective, missionName);
    if (count !== null) payload.totalCountRequired = count;
    stepDescription = count ? `Attempt crafting ${count} times` : 'Attempt crafting';
  } else if (objective.toLowerCase().includes('mine') && objective.toLowerCase().includes('point')) {
    objectiveType = 'MiningPoints';
    const count = extractCount(objective, missionName);
    if (count !== null) payload.totalCountRequired = count;
    stepDescription = count ? `Earn ${count} mining points` : 'Earn mining points';
  } else if (objective.toLowerCase().includes('mine') && objective.toLowerCase().includes('claim')) {
    objectiveType = 'MiningClaim';
    const count = extractCount(objective, missionName);
    if (count !== null) payload.totalCountRequired = count;
    stepDescription = count ? `Find ${count} mining claims` : 'Find mining claims';
  } else if (objective.toLowerCase().includes('mine')) {
    objectiveType = 'MiningCycle';
    const count = extractCount(objective, missionName);
    if (count !== null) payload.totalCountRequired = count;
    stepDescription = count ? `Mine ${count} cycles` : 'Mine for resources';
  } else if (objective.toLowerCase().includes('talk') || objective.toLowerCase().includes('dialog')) {
    objectiveType = 'Dialog';
    stepDescription = 'Talk to NPCs';
  } else if (objective.toLowerCase().includes('visit') || objective.toLowerCase().includes('explore')) {
    objectiveType = 'Explore';
    stepDescription = 'Visit locations';
  } else if (objective.toLowerCase().includes('hand in') || objective.toLowerCase().includes('deliver') || objective.toLowerCase().includes('turn in')) {
    objectiveType = 'HandIn';
    stepDescription = 'Hand in items';
  } else if (objective.toLowerCase().includes('interact') || objective.toLowerCase().includes('collect') || objective.toLowerCase().includes('gather') || objective.toLowerCase().includes('sweat') || objective.toLowerCase().includes('scan') || objective.toLowerCase().includes('tame') || objective.toLowerCase().includes('heal')) {
    objectiveType = 'Interact';
    stepDescription = 'Interact with environment';
  } else {
    objectiveType = 'Dialog';
    stepDescription = 'Complete mission objective';
  }

  // Parse rewards
  const { items, skills, isChoice } = parseRewards(mission.reward, skillNamesList);

  result[missionName] = {
    stepDescription,
    objective: { type: objectiveType, payload },
    rewardItems: items,
    rewardSkills: skills,
    rewardIsChoice: isChoice
  };
}

console.log(`Analyzed ${Object.keys(result).length} missions`);
fs.writeFileSync('tools/data import/missions/analysis-batch-5.json', JSON.stringify(result, null, 2));
console.log('Analysis complete. Results written to analysis-batch-5.json');
