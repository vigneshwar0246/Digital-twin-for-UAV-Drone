import { Vector3, MathUtils } from 'three';
export const ENGINE_ANCHOR = new Vector3(1.45,0,0);
export function cameraPose(zoom, aspect, flight) {
  const narrow = aspect < 1.1;
  const wide = new Vector3(narrow?10:8, (narrow?9:6.5)+Math.sin(flight*Math.PI)*0.3, narrow?19:12);
  const close = new Vector3(1.225,0.875,1.575).multiplyScalar(narrow?1.8:1).add(ENGINE_ANCHOR);
  const t = MathUtils.smoothstep(zoom,0,1);
  return { position:wide.lerp(close,t), target:new Vector3(narrow?0:0.2,0,0).lerp(ENGINE_ANCHOR,t), fov:MathUtils.lerp(narrow?48:38,35,t), opacity:MathUtils.lerp(1,0.1,MathUtils.smoothstep(zoom,0.12,0.88)) };
}
