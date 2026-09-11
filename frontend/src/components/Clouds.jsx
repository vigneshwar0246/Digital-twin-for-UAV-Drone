import { useRef, useMemo, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import { CanvasTexture } from 'three';
export default function Clouds({motion}){
 const texture=useMemo(()=>{const canvas=document.createElement('canvas');canvas.width=128;canvas.height=128;const ctx=canvas.getContext('2d');const g=ctx.createRadialGradient(64,64,0,64,64,64);g.addColorStop(0,'rgba(255,255,255,0.5)');g.addColorStop(.4,'rgba(255,255,255,0.22)');g.addColorStop(1,'rgba(255,255,255,0)');ctx.fillStyle=g;ctx.fillRect(0,0,128,128);return new CanvasTexture(canvas);},[]);
 useEffect(()=>()=>texture.dispose(),[texture]);
 const group=useRef();useFrame(()=>{group.current.position.x=-motion.flight*1.5;group.current.position.y=-2.4+motion.zoom*0.8;});
 return <group ref={group} position={[0,-2.4,-4]}>{[[-6,0,-2,12],[4,-0.5,-3,16],[9,1,-6,10]].map(([x,y,z,s],i)=><sprite key={i} position={[x,y,z]} scale={[s,s*.28,1]}><spriteMaterial map={texture} color={i===1?'#e8a57c':'#b9b6a8'} transparent opacity={0.5} depthWrite={false}/></sprite>)}</group>;
}
