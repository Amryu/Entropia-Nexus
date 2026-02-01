//@ts-nocheck
export async function load(event) {
  return {
    session: event.locals.session,
    // Device detection info from hooks.server.js
    initialViewportWidth: event.locals.initialViewportWidth,
    isMobileDevice: event.locals.isMobileDevice
  }
}