import { useMemo, useRef, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { aircraftPose } from '../animation/aircraftTimeline';
import Propeller from './Propeller';
import Engine from './Engine';
function wingGeometry(){
 const shape=new THREE.Shape();shape.moveTo(-0.7,0);shape.lineTo(-0.35,5.5);shape.lineTo(0.05,5.65);shape.lineTo(0.5,0);shape.closePath();
 const geo=new THREE.ExtrudeGeometry(shape,{depth:0.055,bevelEnabled:true,bevelSegments:2,steps:1,bevelSize:0.035,bevelThickness:0.02});geo.rotateX(Math.PI/2);return geo;
}
export default function Aircraft({motion,onSelect}){
 const root=useRef(),shell=useRef(),highlight=useRef(); const wing=useMemo(wingGeometry,[]);
 const edges=useMemo(()=>new THREE.EdgesGeometry(wing,25),[wing]);
 useEffect(()=>()=>edges.dispose(),[edges]);
 useEffect(()=>()=>wing.dispose(),[wing]);
 useFrame(({gl})=>{
   const [x,y,yaw,bank]=aircraftPose(motion.flight);root.current.position.set(x,y,0);root.current.rotation.set(bank,yaw,0.015*Math.sin(motion.flight*Math.PI*2));
   highlight.current.visible=motion.flight>=0.995&&motion.zoom<0.1&&(motion.hover||motion.pulse>0);
   gl.domElement.style.cursor=motion.flight>=0.995&&!motion.selected&&motion.hover?'pointer':'auto';
   const opacity=1-0.9*THREE.MathUtils.smoothstep(motion.zoom,0.12,0.88);
   shell.current.traverse(o=>{if(o.isMesh){o.material.opacity=opacity;o.material.depthWrite=opacity>0.95;o.material.emissive?.set(motion.hover||motion.pulse>0?'#44220c':'#000000');}});
 });
 const metal=<meshStandardMaterial color="#b6bdbb" metalness={0.72} roughness={0.34} transparent/>;
 return <group ref={root} name="aircraft-placeholder" onClick={e=>{e.stopPropagation();onSelect();}} onPointerOver={()=>{motion.hover=true;}} onPointerOut={()=>{motion.hover=false;}}>
 <group ref={shell}>
  <mesh scale={[3.05,0.37,0.41]}>{metal}<sphereGeometry args={[1,48,24]}/></mesh>
  <mesh position={[1.4,0,0]} scale={[1.12,0.39,0.48]}><sphereGeometry args={[1,48,24]}/>{metal}</mesh>
  <mesh position={[-1.58,0.25,0]} scale={[0.75,0.24,0.32]}><sphereGeometry args={[1,32,16]}/><meshStandardMaterial color="#333d41" metalness={0.48} roughness={0.22} transparent/></mesh>
  {[1,-1].map(side=><group key={side} scale={[1,1,side]} position={[-0.08,0.03,0]}><mesh geometry={wing}>{metal}</mesh><mesh position={[0.09,0.006,-4.55]}><boxGeometry args={[0.35,0.067,0.065]}/><meshStandardMaterial color="#e56f38" transparent/></mesh></group>)}
  {[-1,1].map(side=><group key={side} position={[1.25,-0.03,side*1.45]}>
    <mesh position={[0.48,0,0]} scale={[1.55,0.07,0.075]}><sphereGeometry args={[1,24,12]}/>{metal}</mesh>
    <mesh position={[1.52,0.43,-side*0.21]} rotation={[side*0.5,0,0.15]}><boxGeometry args={[0.72,0.88,0.05]}/>{metal}</mesh>
  </group>)}
  <mesh position={[2.65,0,0]}><boxGeometry args={[0.5,0.055,2.9]}/>{metal}</mesh>
  <mesh position={[-1.4,-0.4,0]}><sphereGeometry args={[0.17,20,16]}/><meshStandardMaterial color="#626b6c" metalness={0.6} roughness={0.3} transparent/></mesh>
 </group><group ref={highlight} visible={false}>{[1,-1].map(side=><lineSegments key={side} geometry={edges} position={[-0.08,0.032,0]} scale={[1,1,side]}><lineBasicMaterial color="#e98240" transparent opacity={0.8}/></lineSegments>)}<mesh position={[1.45,0,0]} rotation={[0,Math.PI/2,0]}><torusGeometry args={[0.57,0.009,8,64]}/><meshBasicMaterial color="#de7a3e" transparent opacity={0.75}/></mesh></group><Propeller motion={motion}/><Engine/>
 </group>;
}
