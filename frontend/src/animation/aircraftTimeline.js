import { MathUtils } from 'three';
const frames = [[5.7,0.4,0.3,-0.13],[4.2,0.55,0.18,-0.08],[0.1,0.25,-0.12,0.08],[-0.65,0.08,0.08,0.035],[0,0,0,0]];
export function aircraftPose(progress) {
  const scaled = Math.min(1,Math.max(0,progress))*4;
  const i = Math.min(3,Math.floor(scaled));
  const t = MathUtils.smoothstep(scaled-i,0,1);
  return frames[i].map((v,j)=>MathUtils.lerp(v,frames[i+1][j],t));
}
