import { browser } from '$app/environment';
import { activateAdConsent, activateAnalyticsConsent } from '$lib/revenue-loader.js';

const ADS_KEY = 'nexus.consent.ads';
const ANALYTICS_KEY = 'nexus.consent.analytics';

/** Log consent decision server-side for GDPR compliance. */
function logConsent(ads, analytics) {
	if (!browser) return;
	const payload = JSON.stringify({ ads, analytics });
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
/** @type {'granted' | 'denied' | null} */
let _analyticsConsent = $state(null);

// Initialize from localStorage on browser
if (browser) {
	try {
		const storedAds = localStorage.getItem(ADS_KEY);
		if (storedAds === 'granted' || storedAds === 'denied') {
			_adsConsent = storedAds;
		}
		const storedAnalytics = localStorage.getItem(ANALYTICS_KEY);
		if (storedAnalytics === 'granted' || storedAnalytics === 'denied') {
			_analyticsConsent = storedAnalytics;
		}
		// Returning visitor with consent - activate
		if (storedAds === 'granted') {
			activateAdConsent();
		}
		if (storedAnalytics === 'granted') {
			activateAnalyticsConsent();
		}
	} catch {}
}

export function getAdsConsent() {
	return _adsConsent;
}

export function getAnalyticsConsent() {
	return _analyticsConsent;
}

export function hasDecision() {
	return _adsConsent !== null && _analyticsConsent !== null;
}

export function grantAds() {
	_adsConsent = 'granted';
	if (!browser) return;
	try {
		localStorage.setItem(ADS_KEY, 'granted');
		// Suppress Ko-fi prompt - no double-dipping support requests
		localStorage.setItem('nexus.kofi.dismissed', '1');
	} catch {}
	activateAdConsent();
}

export function denyAds() {
	_adsConsent = 'denied';
	if (!browser) return;
	try {
		localStorage.setItem(ADS_KEY, 'denied');
	} catch {}
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
	grantAds();
	grantAnalytics();
	logConsent('granted', 'granted');
}

/**
 * Deny all non-essential consent categories at once.
 */
export function denyAll() {
	denyAds();
	denyAnalytics();
	logConsent('denied', 'denied');
}

/**
 * Save granular consent settings.
 * @param {{ ads: boolean, analytics: boolean }} settings
 */
export function saveConsent(settings) {
	if (settings.ads) grantAds(); else denyAds();
	if (settings.analytics) grantAnalytics(); else denyAnalytics();
	logConsent(
		settings.ads ? 'granted' : 'denied',
		settings.analytics ? 'granted' : 'denied'
	);
}

/**
 * Reset consent (for "change preferences" UI).
 */
export function resetConsent() {
	_adsConsent = null;
	_analyticsConsent = null;
	if (!browser) return;
	try {
		localStorage.removeItem(ADS_KEY);
		localStorage.removeItem(ANALYTICS_KEY);
	} catch {}
}
