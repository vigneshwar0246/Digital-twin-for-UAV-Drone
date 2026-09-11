import { Canvas, useFrame } from '@react-three/fiber';
import { Environment, Lightformer } from '@react-three/drei';
import { cameraPose } from '../animation/engineZoom';
import Aircraft from './Aircraft';
import Clouds from './Clouds';
function CameraRig({motion}){useFrame(({camera,size})=>{const p=cameraPose(motion.zoom,size.width/size.height,motion.flight);camera.position.copy(p.position);camera.lookAt(p.target);camera.fov=p.fov;camera.updateProjectionMatrix();});return null;}
export default function UAVScene({motion,onSelect}){
 return <Canvas dpr={[1,1.5]} camera={{position:[8,6.5,12],fov:38,near:0.05,far:150}} gl={{antialias:true,alpha:true,powerPreference:'high-performance'}}>
  <ambientLight intensity={0.8}/><directionalLight position={[-4,9,5]} intensity={3.2} color="#fff7ea"/><directionalLight position={[5,2,-4]} intensity={2} color="#d6e0e2"/>
  <Environment resolution={128}><Lightformer position={[0,8,0]} rotation={[Math.PI/2,0,0]} scale={[20,20,1]} intensity={3}/><Lightformer position={[-8,3,0]} rotation={[0,Math.PI/2,0]} scale={[10,5,1]} intensity={2}/></Environment>
  <CameraRig motion={motion}/><Clouds motion={motion}/><Aircraft motion={motion} onSelect={onSelect}/>
 </Canvas>;
}
