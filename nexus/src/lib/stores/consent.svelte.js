import { browser } from '$app/environment';
import { loadRevenueScript, activateConsent } from '$lib/revenue-loader.js';

const STORAGE_KEY = 'nexus.consent.ads';

/** Log consent decision server-side for GDPR compliance. */
function logConsent(ads) {
	if (!browser) return;
	const payload = JSON.stringify({ ads });
	try {
		const blob = new Blob([payload], { type: 'application/json' });
		navigator.sendBeacon('/api/site-pref', blob);
	} catch {
		fetch('/api/site-pref', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: payload,
		}).catch(() => {});
	}
}

/** @type {'granted' | 'denied' | null} */
let _adsConsent = $state(null);

// Initialize from localStorage on browser
if (browser) {
	try {
		const stored = localStorage.getItem(STORAGE_KEY);
		if (stored === 'granted' || stored === 'denied') {
			_adsConsent = stored;
		}
		// Returning visitor with consent - activate and load script
		if (stored === 'granted') {
			activateConsent();
			loadRevenueScript();
		}
	} catch {}
}

export function getAdsConsent() {
	return _adsConsent;
}

export function hasDecision() {
	return _adsConsent === 'granted' || _adsConsent === 'denied';
}

export function grantAds() {
	_adsConsent = 'granted';
	if (!browser) return;
	try {
		localStorage.setItem(STORAGE_KEY, 'granted');
		// Suppress Ko-fi prompt - no double-dipping support requests
		localStorage.setItem('nexus.kofi.dismissed', '1');
	} catch {}
	activateConsent();
	loadRevenueScript();
	logConsent('granted');
}

export function denyAds() {
	_adsConsent = 'denied';
	if (!browser) return;
	try {
		localStorage.setItem(STORAGE_KEY, 'denied');
	} catch {}
	logConsent('denied');
}

/**
 * Save granular consent settings.
 * @param {{ ads: boolean }} settings
 */
export function saveConsent(settings) {
	if (settings.ads) {
		grantAds();
	} else {
		denyAds();
	}
}

/**
 * Reset consent (for "change preferences" UI).
 */
export function resetConsent() {
	_adsConsent = null;
	if (!browser) return;
	try {
		localStorage.removeItem(STORAGE_KEY);
	} catch {}
}
