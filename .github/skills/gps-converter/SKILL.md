---
name: gps-converter
description: Converts EXIF GPS rational numbers to decimal degrees for Leaflet.js.
---
# Instructions
1. Read the GPS latitude/longitude rational tuples from EXIF.
2. Extract the 'Ref' (N/S/E/W) to determine sign (+/-).
3. Apply the formula: $Degrees + (Minutes / 60) + (Seconds / 3600)$.
4. Return a JSON object: `{ "lat": float, "lng": float }`.