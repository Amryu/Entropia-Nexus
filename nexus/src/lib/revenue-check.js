/**
 * Detect whether ad content is being blocked.
 * Uses multiple signals for reliable detection.
 * @returns {Promise<boolean>} true if ads appear blocked
 */
export async function checkRevenueBlocked() {
	// Signal 1: Try to fetch the ad script - adblockers intercept this network request.
	// This is the most reliable signal since it doesn't depend on script load timing.
	try {
		await fetch(
			'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js',
			{ method: 'HEAD', mode: 'no-cors', cache: 'no-store' }
		);
		// no-cors fetch returns opaque response (status 0) on success,
		// but throws on network-level block
	} catch {
		return true;
	}

	// Signal 2: Bait element probe - create elements that filter lists target
	return new Promise((resolve) => {
		const bait = document.createElement('div');
		bait.innerHTML = '&nbsp;';
		bait.className = 'adsbox ad-placement ad-banner';
		bait.style.cssText = 'position:absolute;top:-9999px;left:-9999px;width:1px;height:1px;';
		document.body.appendChild(bait);

		// Give filter lists time to act
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
