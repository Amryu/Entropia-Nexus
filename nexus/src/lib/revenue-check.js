/**
 * Detect whether ad content is being blocked.
 * Uses multiple signals: script global check + bait element probe.
 * Only meaningful after consent has been granted and script load attempted.
 * @returns {Promise<boolean>} true if ads appear blocked
 */
export async function checkRevenueBlocked() {
	// Signal 1: Check if the ad script global exists
	if (typeof /** @type {any} */ (window).adsbygoogle === 'undefined') {
		return true;
	}

	// Signal 2: Bait element probe - create an element that filter lists target
	return new Promise((resolve) => {
		const bait = document.createElement('div');
		bait.className = 'textads banner-ads';
		bait.setAttribute('data-ad-slot', 'test');
		bait.style.cssText = 'position:absolute;top:-9999px;left:-9999px;width:1px;height:1px;';
		document.body.appendChild(bait);

		setTimeout(() => {
			const blocked =
				bait.offsetHeight === 0 ||
				bait.offsetParent === null ||
				getComputedStyle(bait).display === 'none' ||
				getComputedStyle(bait).visibility === 'hidden';

			bait.remove();
			resolve(blocked);
		}, 500);
	});
}
