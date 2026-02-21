// @ts-nocheck
import { redirect } from '@sveltejs/kit';

export async function load({ locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  if (!realUser?.administrator) {
    throw redirect(302, '/tools');
  }
}
