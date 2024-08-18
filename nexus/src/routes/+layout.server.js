//@ts-nocheck
export async function load(event) {
  return {
    session: event.locals.session
  }
}