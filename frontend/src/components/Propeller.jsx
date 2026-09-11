import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
export default function Propeller({motion}){
 const rotor=useRef(),root=useRef();
 useFrame((_,delta)=>{if(rotor.current)rotor.current.rotation.x+=Math.min(delta,0.05)*32;root.current.traverse(o=>{if(o.isMesh){o.material.userData.base??=o.material.opacity;o.material.transparent=true;o.material.opacity=o.material.userData.base*(1-motion.zoom*.96);o.material.depthWrite=motion.zoom<.1;}});});
 return <group ref={root} position={[2.75,0,0]}><mesh rotation={[0,0,Math.PI/2]}><cylinderGeometry args={[0.1,0.14,0.25,20]}/><meshStandardMaterial color="#424b4b" metalness={0.7} roughness={0.3}/></mesh><group ref={rotor}>{[0,Math.PI/2].map(a=><mesh key={a} rotation={[a,0,0]}><boxGeometry args={[0.035,1.95,0.095]}/><meshStandardMaterial color="#424847" transparent opacity={0.35} metalness={0.5} roughness={0.4}/></mesh>)}</group><mesh rotation={[0,Math.PI/2,0]}><circleGeometry args={[1,48]}/><meshBasicMaterial color="#67706b" transparent opacity={0.055} depthWrite={false} side={2}/></mesh></group>;
}
