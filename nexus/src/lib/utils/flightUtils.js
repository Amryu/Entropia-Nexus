/**
 * Shared flight utility functions for flight management
 */

/**
 * Check if a flight is within the restore grace period (2h after scheduled departure)
 * @param {Object} flight - Flight object with status and scheduled_departure
 * @returns {boolean}
 */
function isWithinRestoreGracePeriod(flight) {
  if (flight.status !== 'cancelled' || !flight.scheduled_departure) return false;
  const scheduledDeparture = new Date(flight.scheduled_departure);
  const now = new Date();
  const gracePeriodEnd = new Date(scheduledDeparture.getTime() + 2 * 60 * 60 * 1000);
  return now < gracePeriodEnd;
}

/**
 * Check if a flight would overlap with any active flights (within 15 minutes)
 * @param {Object} flight - Flight to check
 * @param {Array} activeFlights - Array of active flights to check against
 * @returns {boolean} - True if there's an overlap
 */
export function hasFlightOverlap(flight, activeFlights) {
  if (!flight.scheduled_departure) return false;

  const flightTime = new Date(flight.scheduled_departure).getTime();

  for (const activeFlight of activeFlights) {
    // Skip comparing flight with itself
    if (activeFlight.id === flight.id) continue;

    const activeTime = new Date(activeFlight.scheduled_departure).getTime();
    const diffMs = Math.abs(flightTime - activeTime);
    const diffMinutes = diffMs / (1000 * 60);

    if (diffMinutes < 15) {
      return true; // Would overlap within 15 minutes
    }
  }

  return false;
}

/**
 * Check if a cancelled flight can be restored
 * Checks both grace period and overlap with active flights
 * @param {Object} flight - Flight to check
 * @param {Array} activeFlights - Array of active flights to check against
 * @returns {boolean}
 */
export function canRestoreFlight(flight, activeFlights) {
  if (!isWithinRestoreGracePeriod(flight)) return false;
  if (hasFlightOverlap(flight, activeFlights)) return false;
  return true;
}

/**
 * Format a flight time for display
 * @param {string|Date} dateString - Flight departure time
 * @returns {string}
 */
export function formatFlightTime(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffMinutes = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMinutes < 0) return date.toLocaleString();
  if (diffDays > 0) return `In ${diffDays} day${diffDays > 1 ? 's' : ''} (${date.toLocaleString()})`;
  if (diffHours > 0) return `In ${diffHours} hour${diffHours > 1 ? 's' : ''} ${diffMinutes % 60} min`;
  return `In ${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''}`;
}

/**
 * Check if a user can check in to a flight (within 7 days before departure)
 * @param {Object} flight - Flight object with scheduled_departure
 * @returns {boolean}
 */
export function canCheckIn(flight) {
  if (!flight.scheduled_departure) return false;
  if (flight.status !== 'scheduled' && flight.status !== 'boarding') return false;

  const departureTime = new Date(flight.scheduled_departure);
  const now = new Date();
  const diffMs = departureTime.getTime() - now.getTime();
  const diffMinutes = diffMs / (1000 * 60);
  const sevenDaysInMinutes = 7 * 24 * 60;

  // Check-in opens 7 days before, closes at departure
  return diffMinutes <= sevenDaysInMinutes && diffMinutes >= 0;
}

/**
 * Convert a date to datetime-local input format
 * @param {string|Date} dateString - Date to format
 * @returns {string} - Format: YYYY-MM-DDTHH:MM
 */
export function toDateTimeLocalFormat(dateString) {
  const d = new Date(dateString);
  const pad = n => n.toString().padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
