import { checkRevenueBlocked } from '$lib/revenue-check.js';
import { loadRevenueScript } from '$lib/revenue-loader.js';

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
 * Should be called after consent is granted and the revenue script load has been attempted.
 */
export async function runRevenueCheck() {
	if (_checked) return;
	try {
		// Ensure script load has been attempted before checking
		await loadRevenueScript().catch(() => {});
		// Small extra delay for filter lists to act
		await new Promise((r) => setTimeout(r, 300));
		_blocked = await checkRevenueBlocked();
	} catch {
		_blocked = true;
	}
	_checked = true;
}
