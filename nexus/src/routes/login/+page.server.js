// @ts-nocheck

export async function load({ locals }) {
  // Check if we're in test mode (NODE_ENV=test)
  const isTestMode = process.env.NODE_ENV === 'test';

  // If already logged in, could redirect to home
  if (locals.session?.user) {
    return {
      isTestMode,
      user: locals.session.user
    };
  }

  return {
    isTestMode
  };
}
