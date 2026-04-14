import { browser } from '$app/environment';
import { activateAnalyticsConsent } from '$lib/revenue-loader.js';

const ANALYTICS_KEY = 'nexus.consent.analytics';

/** Log consent decision server-side for GDPR compliance. */
function logConsent(analytics) {
	if (!browser) return;
	const payload = JSON.stringify({ analytics });
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
let _analyticsConsent = $state(null);

// Initialize from localStorage on browser
if (browser) {
	try {
		const storedAnalytics = localStorage.getItem(ANALYTICS_KEY);
		if (storedAnalytics === 'granted' || storedAnalytics === 'denied') {
			_analyticsConsent = storedAnalytics;
		}
		if (storedAnalytics === 'granted') {
			activateAnalyticsConsent();
		}
	} catch {}
}

export function getAnalyticsConsent() {
	return _analyticsConsent;
}

export function hasDecision() {
	return _analyticsConsent !== null;
}

export function grantAnalytics() {
	_analyticsConsent = 'granted';
	if (!browser) return;
	try {
		localStorage.setItem(ANALYTICS_KEY, 'granted');
	} catch {}
	activateAnalyticsConsent();
}

export function denyAnalytics() {
	_analyticsConsent = 'denied';
	if (!browser) return;
	try {
		localStorage.setItem(ANALYTICS_KEY, 'denied');
	} catch {}
}

/**
 * Grant all consent categories at once.
 */
export function grantAll() {
	grantAnalytics();
	logConsent('granted');
}

/**
 * Deny all non-essential consent categories at once.
 */
export function denyAll() {
	denyAnalytics();
	logConsent('denied');
}

/**
 * Save granular consent settings.
 * @param {{ analytics: boolean }} settings
 */
export function saveConsent(settings) {
	if (settings.analytics) grantAnalytics(); else denyAnalytics();
	logConsent(settings.analytics ? 'granted' : 'denied');
}

/**
 * Reset consent (for "change preferences" UI).
 */
export function resetConsent() {
	_analyticsConsent = null;
	if (!browser) return;
	try {
		localStorage.removeItem(ANALYTICS_KEY);
	} catch {}
}
