// @ts-nocheck
export const ssr = false;
export async function load() {
	// Defer data fetching to the client component for instant render with a spinner
	return { categorizedItems: null };
}
