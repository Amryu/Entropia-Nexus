class Player {
  constructor(id, name) {
    this.id = id;
    this.name = name;
    this.planet = null;
    this.location = null;
    this.skills = {
      melee: 0,
      ranged: 0,
      neuro: 0,
      defense: 0,
      constitution: 0,
      resonance: 0,
      synthesizing: 0,
      engineering: 0,
      smithing: 0,
      construction: 0,
      mining: 0,
      forestry: 0,
      fishing: 0,
      farming: 0,
      cooking: 0,
    };
    this.equipment = {
      head: null,
      body: null,
      legs: null,
      feet: null,
      hands: null,
      weapon: null,
      shield: null,
      ammo: null,
      back: null,
      amulet: null,
      ring: null,
      implant: null,
    };
    this.inventory = {};
    this.bank = {};
    this.ent = 0;
    this.activity = null;

    this.health = 100;
    this.resonance = 10;
  }

  tick() {
    this.activity?.tick(); // Call the tick method of the current activity if it exists
  }

  start

  combatStats() {
    return {
      currentHealth: this.health,
      currentResonance: this.resonance * 10,
      melee: this.skills.melee,
      ranged: this.skills.ranged,
      neuro: this.skills.neuro,
      defense: this.skills.defense,
      constitution: this.skills.constitution,
      resonance: this.skills.resonance,
      fortification: this.equipment.map((item) => item.fortification || 0).reduce((a, b) => a + b, 0),
      meleeAccuracy: this.equipment.map((item) => item.meleeAccuracy || 0).reduce((a, b) => a + b, 0),
      meleeStrength: this.equipment.map((item) => item.meleeStrength || 0).reduce((a, b) => a + b, 0),
      rangedAccuracy: this.equipment.map((item) => item.rangedAccuracy || 0).reduce((a, b) => a + b, 0),
      rangedStrength: this.equipment.map((item) => item.rangedStrength || 0).reduce((a, b) => a + b, 0),
      neuroAccuracy: this.equipment.map((item) => item.neuroAccuracy || 0).reduce((a, b) => a + b, 0),
      neuroStrength: this.equipment.map((item) => item.neuroStrength || 0).reduce((a, b) => a + b, 0),
      resonanceRegeneration: this.equipment.map((item) => item.resonanceRegeneration || 0).reduce((a, b) => a + b, 0),
      resonanceEndurance: this.equipment.map((item) => item.resonanceEndurance || 0).reduce((a, b) => a + b, 0),
      resonancePower: this.equipment.map((item) => item.resonancePower || 0).reduce((a, b) => a + b, 0),
      slashingDefense: this.equipment.map((item) => item.slashingDefense || 0).reduce((a, b) => a + b, 0),
      piercingDefense: this.equipment.map((item) => item.piercingDefense || 0).reduce((a, b) => a + b, 0),
      concussiveDefense: this.equipment.map((item) => item.crushingDefense || 0).reduce((a, b) => a + b, 0),
      penetrationDefense: this.equipment.map((item) => item.penetrationDefense || 0).reduce((a, b) => a + b, 0),
      neuroDefense: this.equipment.map((item) => item.neuroDefense || 0).reduce((a, b) => a + b, 0),
      combustionDefense: this.equipment.map((item) => item.combustionDefense || 0).reduce((a, b) => a + b, 0),
      shockDefense: this.equipment.map((item) => item.shockDefense || 0).reduce((a, b) => a + b, 0),
      corrosiveDefense: this.equipment.map((item) => item.corrosiveDefense || 0).reduce((a, b) => a + b, 0),
      frostDefense: this.equipment.map((item) => item.frostDefense || 0).reduce((a, b) => a + b, 0),
    };
  }

  attack(target) {
    console.log(`${this.name} attacks ${target.name}`);

    const playerStats = this.combatStats();
    const targetStats = target.combatStats();
    const weapon = this.equipment.weapon || null; // Get the player's weapon from equipment

    let hitChance = this.getHitChance(weapon, target); // Calculate hit chance based on weapon and target stats

    let damage = 0;

    if (Math.random() * 100 < hitChance) {
      // If the attack hits
      if (weapon === null || weapon.class === 'melee') {
        damage = Math.max(Math.floor(Math.random() * (playerStats.meleeStrength / 5)), 1);
      } else if (weapon.class === 'ranged') {
        damage = Math.max(Math.floor(Math.random() * (playerStats.rangedStrength / 5)), 1);
      } else if (weapon.class === 'neuro') {
        damage = Math.max(Math.floor(Math.random() * (playerStats.neuroStrength / 5)), 1);
      }
    } else {
      return 0;
    }

    damage = Math.max(0, damage - targetStats.fortification); // Apply fortification to damage

    // TODO apply buffs etc.

    target.takeDamage(damage, { source: this }); // Apply damage to target
  }

  getHitChance(weapon, enemy) {
    const playerStats = this.combatStats();
    const targetStats = enemy.combatStats(); // Get the target's combat stats

    let accuracy = 0;
    let defense = 0;
  
    // Determine accuracy based on weapon class
    if (weapon.class === 'melee') {
      accuracy = playerStats.meleeAccuracy + this.skills.melee * 0.5;
      defense = enemy.defense('melee', weapon.style);
    } else if (weapon.class === 'ranged') {
      accuracy = playerStats.rangedAccuracy + this.skills.ranged * 0.5;
      defense = enemy.defense('ranged', weapon.style);
    } else if (weapon.class === 'neuro') {
      accuracy = playerStats.neuroAccuracy + this.skills.neuro * 0.5;
      defense = enemy.defense('neuro', weapon.style);
    }

    return hitChance = (accuracy / (accuracy + defense)) * 100;
  }

  getDefense(attackClass, attackStyle) {
    const playerStats = this.combatStats();
    let styleDefense = 0;

    switch (attackStyle) {
      case 'slashing':
        styleDefense = playerStats.slashingDefense;
        break;
      case 'piercing':
        styleDefense = playerStats.piercingDefense;
        break;
      case 'concussive':
        styleDefense = playerStats.concussiveDefense;
        break;
      case 'penetration':
        styleDefense = playerStats.penetrationDefense;
        break;
      case 'combustion':
        styleDefense = playerStats.combustionDefense;
        break;
      case 'shock':
        styleDefense = playerStats.shockDefense;
        break;
      case 'corrosive':
        styleDefense = playerStats.corrosiveDefense;
        break;
      case 'frost':
        styleDefense = playerStats.frostDefense;
        break;
      default:
        styleDefense = 0; // Default to 0 if no matching style found
        break;
    }

    let classDefense = 0;

    switch (attackClass) {
      case 'melee':
        this.skills.defense * 0.7 + this.skills.melee * 0.3;
        break;
      case 'ranged':
        classDefense = this.skills.defense * 0.7 + this.skills.ranged * 0.3;
        break;
      case 'neuro':
        classDefense = this.skills.defense * 0.7 + this.skills.neuro * 0.3;
        break;
      default:
        classDefense = 0; // Default to 0 if no matching class found
        break;
    }

    return styleDefense + classDefense;
  }

  // Static method to create a Player instance from a JSON object
  static fromJSON(json) {
    const player = new Player();
    Object.assign(player, json); // Copy properties from the JSON object to the Player instance
    return player;
  }
}

module.exports = Player;