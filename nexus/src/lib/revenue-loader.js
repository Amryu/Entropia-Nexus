/**
 * Update Google Consent Mode v2 to grant ad-related consent.
 * Called when the user explicitly consents to personalized ads.
 * The AdSense script is always loaded (in app.html) but defaults to
 * non-personalized ads via Consent Mode defaults.
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
