/**
 * Google Maps driving-directions link.
 *
 * Coordinates are preferred over a text destination so the link does not change
 * meaning if Google's database of place names changes. `destinationText` is a
 * fallback for locations we could not geocode to a coordinate we trust; passing
 * nothing keeps the historical behaviour of returning null, which callers render
 * as plain text instead of a link.
 *
 * @param {string} origin - "lat,lon"
 * @param {number[] | undefined} coordinates - [lon, lat] as stored in the *-locations.json files
 * @param {string} [destinationText] - street address to fall back to
 * @returns {string | null}
 */
export function getDirectionsUrl(origin, coordinates, destinationText) {
  const destination =
    Array.isArray(coordinates) && coordinates.length == 2
      ? `${coordinates[1]},${coordinates[0]}`
      : (destinationText ?? "");

  if (destination == "") {
    return null;
  }

  return "https://www.google.com/maps/dir/?api=1"
    + `&origin=${encodeURIComponent(origin)}`
    + `&destination=${encodeURIComponent(destination)}`
    + "&travelmode=driving";
}
