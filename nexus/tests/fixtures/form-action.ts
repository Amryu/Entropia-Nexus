import type { APIResponse } from '@playwright/test';

/**
 * Extract redirect location from a SvelteKit form action response.
 *
 * SvelteKit form actions return redirects differently depending on request context:
 * - Standard form submissions: raw HTTP 302/303 with Location header
 * - Fetch-style requests (e.g. Playwright page.request): HTTP 200 with JSON body
 *   { type: "redirect", status: 302, location: "..." }
 *
 * This helper handles both formats transparently.
 */
export async function extractFormActionRedirect(response: APIResponse): Promise<string> {
  if ([302, 303].includes(response.status())) {
    const location = response.headers()['location'];
    if (location) return location;
  }

  if (response.status() === 200) {
    const body = await response.json();
    if (body.type === 'redirect' && body.location) {
      return body.location;
    }
  }

  throw new Error(`Expected redirect from form action, got status ${response.status()}`);
}
