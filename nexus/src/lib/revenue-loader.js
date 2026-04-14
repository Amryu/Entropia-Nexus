function gtag() {
	if (typeof window === 'undefined') return;
	/** @type {any} */ (window).dataLayer = /** @type {any} */ (window).dataLayer || [];
	/** @type {any} */ (window).dataLayer.push(arguments);
}

/**
 * Update Google Consent Mode v2 to grant analytics consent.
 * Called when the user explicitly consents to analytics tracking.
 * GA4 is always loaded (in app.html) but defaults to cookieless
 * mode via Consent Mode defaults.
 */
export function activateAnalyticsConsent() {
	gtag('consent', 'update', {
		'analytics_storage': 'granted'
	});
}
