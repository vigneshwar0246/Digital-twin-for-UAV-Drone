export const STATES = Object.freeze({ INTRO:'INTRO', FLIGHT:'AIRCRAFT_FLIGHT', SETTLED:'AIRCRAFT_SETTLED', SELECTED:'AIRCRAFT_SELECTED', ZOOM:'ENGINE_ZOOM', HERO:'ENGINE_HERO' });
export function resolveState(flight, zoom, selected) {
  if (flight < 0.005) return STATES.INTRO;
  if (flight < 0.995) return STATES.FLIGHT;
  if (!selected) return STATES.SETTLED;
  if (zoom < 0.005) return STATES.SELECTED;
  return zoom >= 0.995 ? STATES.HERO : STATES.ZOOM;
}
export function canSelect(flight, selected) { return flight >= 0.995 && !selected; }
export function createMotion() { return { flight:0, zoom:0, selected:false, hover:false, pulse:0 }; }
