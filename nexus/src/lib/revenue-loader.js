const SCRIPT_URL = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9726361132383377';

let scriptLoaded = false;
let scriptPromise = null;

/**
 * Dynamically load the revenue script. Returns a promise that resolves
 * when loaded or rejects if blocked/errored.
 * @returns {Promise<void>}
 */
export function loadRevenueScript() {
	if (scriptLoaded) return Promise.resolve();
	if (scriptPromise) return scriptPromise;

	scriptPromise = new Promise((resolve, reject) => {
		const el = document.createElement('script');
		el.async = true;
		el.crossOrigin = 'anonymous';
		el.src = SCRIPT_URL;
		el.onload = () => {
			scriptLoaded = true;
			resolve(undefined);
		};
		el.onerror = () => {
			scriptPromise = null;
			reject(new Error('Revenue script blocked'));
		};
		document.head.appendChild(el);
	});

	return scriptPromise;
}

/**
 * Update Google Consent Mode v2 to grant ad-related consent.
 */
export function activateConsent() {
	if (typeof window === 'undefined') return;
	/** @type {any} */ (window).dataLayer = /** @type {any} */ (window).dataLayer || [];
	function gtag() { /** @type {any} */ (window).dataLayer.push(arguments); }
	gtag('consent', 'update', {
		'ad_storage': 'granted',
		'ad_user_data': 'granted',
		'ad_personalization': 'granted'
	});
}

export function isScriptLoaded() {
	return scriptLoaded;
}
