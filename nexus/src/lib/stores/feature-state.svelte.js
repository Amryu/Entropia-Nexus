import { checkContentBlocked } from '$lib/feature-check.js';

let _blocked = $state(false);
let _checked = $state(false);

export function getContentBlocked() {
	return _blocked;
}

export function getContentChecked() {
	return _checked;
}

/**
 * Run the content delivery check.
 * Waits for the delivery script to have time to initialize before probing.
 */
export async function runContentCheck() {
	if (_checked) return;
	try {
		// Wait for the async script to load and slots to initialize
		await new Promise((r) => setTimeout(r, 3000));
		_blocked = await checkContentBlocked();
	} catch {
		_blocked = true;
	}
	_checked = true;
}
