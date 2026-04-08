/**
 * Check whether sponsored content can be displayed.
 * Uses indirect signals that are hard for content filters to target.
 * @returns {Promise<boolean>} true if content delivery appears blocked
 */
export async function checkContentBlocked() {
	// Signal 1: Check if the delivery script loaded and created its global.
	// Wait long enough for the async script (loaded in app.html) to initialize.
	// The global is an array-like object when loaded, undefined when blocked.
	const global = /** @type {any} */ (window).adsbygoogle;
	if (typeof global === 'undefined') {
		return true;
	}

	// Signal 2: Check if any existing slots received content.
	// When the script loads but a filter blocks rendering, slots stay empty.
	const slots = document.querySelectorAll('ins.adsbygoogle');
	if (slots.length > 0) {
		const hasContent = Array.from(slots).some(
			(el) => el.getAttribute('data-ad-status') === 'filled' || el.querySelector('iframe')
		);
		// If slots exist but none filled, rendering is blocked
		if (!hasContent) {
			// Give a bit more time for slow fills
			const filled = await new Promise((resolve) => {
				setTimeout(() => {
					resolve(Array.from(document.querySelectorAll('ins.adsbygoogle')).some(
						(el) => el.getAttribute('data-ad-status') === 'filled' || el.querySelector('iframe')
					));
				}, 2000);
			});
			if (!filled) return true;
		}
	}

	return false;
}
