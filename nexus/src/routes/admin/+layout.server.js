// @ts-nocheck
import { redirect } from '@sveltejs/kit';

export async function load({ locals, url }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  // Must be logged in
  if (!locals.session?.user) {
    const returnUrl = encodeURIComponent(url.pathname + url.search);
    throw redirect(302, `/discord/login?redirect=${returnUrl}`);
  }

  // Must be admin (check realUser for impersonation case)
  if (!realUser?.administrator) {
    throw redirect(302, '/');
  }

  return {
    user: locals.session.user,
    realUser: locals.session.realUser
  };
}
