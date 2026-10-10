import {useEffect,type RefObject} from 'react';
import {cylinderFromEvidence,type FaultVisual} from './FaultVisualizationController';

/** Adapter between semantic diagnostic regions and this procedural SVG model.
 * A future mesh renderer can consume FaultVisual without changing diagnostics. */
export function useFaultSurfaces(ref:RefObject<SVGSVGElement|null>,visuals:FaultVisual[],visible:boolean){
 useEffect(()=>{
  const svg=ref.current;if(!svg)return;
  const nodes=Array.from(svg.querySelectorAll<SVGGElement>('[data-region]'));
  for(const node of nodes){node.removeAttribute('data-fault');node.style.removeProperty('--surface-color');node.style.removeProperty('--surface-opacity');node.querySelectorAll('[data-fault-surface]').forEach(n=>n.remove());}
  const assigned=new Map<SVGGElement,FaultVisual>();
  for(const visual of visuals){
   const cylinder=cylinderFromEvidence(visual.fault);
   let targets=nodes.filter(n=>visual.regions.some(r=>n.dataset.region?.split(' ').includes(r)));
   if(cylinder!==null&&visual.regions.includes('cylinders'))targets=nodes.filter(n=>n.dataset.region?.includes(`cylinder-${cylinder}`));
   if(!targets.length)targets=nodes.filter(n=>n.dataset.region==='engine');
   for(const target of targets)if(!assigned.has(target)||assigned.get(target)!.intensity<visual.intensity)assigned.set(target,visual);
  }
  for(const [node,v] of assigned){
   node.dataset.fault=v.fault.code;node.style.setProperty('--surface-color',v.color);node.style.setProperty('--surface-opacity',String(.2+v.intensity*.38));
   const bounds=node.getBBox();const overlay=document.createElementNS('http://www.w3.org/2000/svg','rect');
   overlay.setAttribute('data-fault-surface','');overlay.setAttribute('x',String(bounds.x));overlay.setAttribute('y',String(bounds.y));overlay.setAttribute('width',String(bounds.width));overlay.setAttribute('height',String(bounds.height));overlay.setAttribute('rx','12');node.appendChild(overlay);
  }
  return()=>{for(const node of nodes){node.removeAttribute('data-fault');node.querySelectorAll('[data-fault-surface]').forEach(n=>n.remove());}};
 },[ref,visuals,visible]);
}
