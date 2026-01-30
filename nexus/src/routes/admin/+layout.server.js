// @ts-nocheck
import { redirect } from '@sveltejs/kit';

export async function load({ locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  // Must be logged in
  if (!locals.session?.user) {
    throw redirect(302, '/login');
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
