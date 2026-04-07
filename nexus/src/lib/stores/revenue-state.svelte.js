import { checkRevenueBlocked } from '$lib/revenue-check.js';

let _blocked = $state(false);
let _checked = $state(false);

export function getRevenueBlocked() {
	return _blocked;
}

export function getRevenueChecked() {
	return _checked;
}

/**
 * Run the adblock detection check.
 * AdSense script is always loaded, so we just need a short delay for filter lists to act.
 */
export async function runRevenueCheck() {
	if (_checked) return;
	try {
		await new Promise((r) => setTimeout(r, 800));
		_blocked = await checkRevenueBlocked();
	} catch {
		_blocked = true;
	}
	_checked = true;
}
