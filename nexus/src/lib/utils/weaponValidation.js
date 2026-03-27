// @ts-nocheck
/**
 * Weapon attachment validation utilities
 * Extracted from loadout manager to maintain parity across services
 */

/**
 * Filters amplifiers that are compatible with the given weapon
 * @param {Array} amplifiers - All available amplifiers
 * @param {Object} weapon - The weapon to match amplifiers for
 * @param {Object} options - Filtering options
 * @param {boolean} options.onlyShowReasonableAmplifiers - Filter out amplifiers that exceed the amp cap (default: false)
 * @returns {Array} Filtered amplifiers compatible with the weapon
 */
export function getCompatibleAmplifiers(amplifiers, weapon, options = {}) {
	const { onlyShowReasonableAmplifiers = false } = options;

	if (!weapon) {
		return [];
	}

	return amplifiers.filter(amplifier => {
		// Get total damage values
		const ampDamage = getTotalDamage(amplifier);
		const weaponDamage = getTotalDamage(weapon);

		if (!ampDamage) {
			return false;
		}

		// Filter overcapped amplifiers (amp damage exceeds 50% of weapon damage)
		if (onlyShowReasonableAmplifiers && 2 * ampDamage > weaponDamage) {
			return false;
		}
		
		// Match amplifier type to weapon class and type
		if (weapon.Properties.Class === 'Ranged') {
			if (weapon.Properties.Type === 'BLP') {
				return amplifier.Properties.Type === 'BLP';
			} else if (weapon.Properties.Type === 'Explosive') {
				return amplifier.Properties.Type === 'Explosive';
			} else if (weapon.Properties.Type?.startsWith('Mining Laser')) {
				return amplifier.Properties.Type === 'Mining';
			} else {
				return amplifier.Properties.Type === 'Energy';
			}
		} else if (weapon.Properties.Class === 'Melee') {
			return amplifier.Properties.Type === 'Melee';
		} else if (weapon.Properties.Class === 'Mindforce') {
			return amplifier.Properties.Type === 'Mindforce';
		}
		
		return false;
	});
}

/**
 * Calculate total damage for a weapon or amplifier
 * @param {Object} item - Weapon or amplifier item
 * @returns {number|null} Total damage or null if not available
 */
function getTotalDamage(item) {
	if (!item?.Properties?.Damage) {
		return null;
	}
	
	const damage = item.Properties.Damage;
	let total = 0;
	let count = 0;
	
	// Sum all damage types
	if (damage.Burn != null) {
		total += damage.Burn;
		count++;
	}
	if (damage.Cold != null) {
		total += damage.Cold;
		count++;
	}
	if (damage.Cut != null) {
		total += damage.Cut;
		count++;
	}
	if (damage.Impact != null) {
		total += damage.Impact;
		count++;
	}
	if (damage.Penetration != null) {
		total += damage.Penetration;
		count++;
	}
	if (damage.Shrapnel != null) {
		total += damage.Shrapnel;
		count++;
	}
	if (damage.Stab != null) {
		total += damage.Stab;
		count++;
	}
	if (damage.Acid != null) {
		total += damage.Acid;
		count++;
	}
	if (damage.Electric != null) {
		total += damage.Electric;
		count++;
	}
	
	return count > 0 ? total : null;
}

/**
 * Check if a weapon supports scopes/sights (ranged weapons only)
 * @param {Object} weapon - The weapon to check
 * @returns {boolean} True if weapon supports scopes/sights
 */
export function supportsScopes(weapon) {
	return weapon?.Properties?.Class === 'Ranged';
}

/**
 * Check if a weapon supports absorbers
 * @param {Object} weapon - The weapon to check
 * @returns {boolean} True if weapon supports absorbers
 */
export function supportsAbsorbers(weapon) {
	// Most weapons support absorbers, but attached weapons (except mounted) don't
	if (!weapon) return false;
	
	// TODO: Add logic for attached weapons if needed
	// For now, assume all weapons support absorbers
	return true;
}

/**
 * Check if a weapon is attached (mounted on vehicles/etc)
 * @param {Object} weapon - The weapon to check
 * @returns {boolean} True if weapon is attached
 */
export function isAttachedWeapon(weapon) {
	// TODO: Implement detection logic if needed
	// This would check if the weapon is a vehicle/robot weapon
	return false;
}
