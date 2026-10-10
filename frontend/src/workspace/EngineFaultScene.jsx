import {Suspense,useEffect,useMemo,useRef,useState} from 'react';
import {Canvas,useFrame,useThree} from '@react-three/fiber';
import {Html,OrbitControls} from '@react-three/drei';
import {Box3,Vector3} from 'three';
import Engine from '../components/Engine';
import {cylinderFromEvidence} from './FaultVisualizationController';

function regionsFor(mesh){
 const names=[];let node=mesh;while(node){names.push(node.name);node=node.parent;}
 if(names.includes('electrical-region'))return ['electrical'];
 if(names.includes('injector'))return ['fuel','timing'];
 if(names.includes('oil-system'))return ['oil'];
 if(names.includes('sensors'))return ['sensors'];
 if(names.some(n=>n.startsWith('cylinders-')))return ['cylinders','heads','cooling','combustion'];
 if(names.includes('crankshaft'))return ['engine','rotating'];
 return ['engine'];
}
function Assembly({visuals,focusCode,resetKey,zoom,choose,reduced}){
 const sceneCamera=useThree(state=>state.camera);
 const previousZoom=useRef(zoom);
 const root=useRef(),controls=useRef(),cameraTarget=useRef(null);const [bindings,setBindings]=useState([]);
 useEffect(()=>{const next=[];root.current.traverse(mesh=>{if(!mesh.isMesh)return;const regions=regionsFor(mesh);let cylinder=null;let node=mesh;while(node){const match=/^cylinders-(-?1)-(0|1)$/.exec(node.name);if(match)cylinder=(match[1]==='-1'?0:2)+Number(match[2])+1;node=node.parent;}
  next.push({mesh,regions,cylinder});});setBindings(next);},[]);
 const applied=useMemo(()=>bindings.map(binding=>({...binding,visual:visuals.filter(v=>v.regions.some(r=>binding.regions.includes(r))&&(cylinderFromEvidence(v.fault)===null||!binding.regions.includes('cylinders')||cylinderFromEvidence(v.fault)===binding.cylinder)).sort((a,b)=>Number(b.fault.code===focusCode)-Number(a.fault.code===focusCode)||b.intensity-a.intensity||Number(b.fault.code==='SENSOR_FAILURE')-Number(a.fault.code==='SENSOR_FAILURE'))[0]})),[bindings,visuals,focusCode]);
 useEffect(()=>{const visual=visuals.find(v=>v.fault.code===focusCode);const cylinder=visual?cylinderFromEvidence(visual.fault):null;const focused=bindings.filter(b=>visual?.regions.some(r=>b.regions.includes(r))&&(cylinder===null||!b.regions.includes('cylinders')||b.cylinder===cylinder));const box=new Box3();for(const b of focused)box.expandByObject(b.mesh);const target=focused.length?box.getCenter(new Vector3()):new Vector3();const size=focused.length?box.getSize(new Vector3()):new Vector3(2,1,2);const distance=Math.max(1.3,Math.max(size.y,size.x/sceneCamera.aspect,size.z)*.7/Math.tan(sceneCamera.fov*Math.PI/360));cameraTarget.current={target,position:target.clone().add(new Vector3(2,1.5,2).normalize().multiplyScalar(focused.length?distance:3.2))};},[focusCode,resetKey,bindings]);
 useEffect(()=>{if(controls.current&&zoom!==previousZoom.current){cameraTarget.current=null;const target=controls.current.target;sceneCamera.position.sub(target).multiplyScalar(previousZoom.current/zoom).add(target);controls.current.update();}previousZoom.current=zoom;},[zoom,sceneCamera]);
 useFrame(({clock,camera},dt)=>{const t=clock.elapsedTime;
  const vibration=Math.max(0,...visuals.map(v=>v.vibration));root.current.position.x=reduced?0:Math.sin(t*32)*vibration*.004;
  for(const {mesh,visual} of applied){mesh.material.emissive.set(visual?(visual.fault.code==='SENSOR_FAILURE'?'#ef2222':visual.color):'#000000');mesh.material.emissiveIntensity=visual?(reduced ? .7 : .5+.35*Math.sin(t*(visual.irregular?4.7:2)+(visual.fault.code==='INJECTION_TIMING_ABNORMALITY'?mesh.id%4:0))+ (visual.irregular ? .15*Math.sin(t*7.3) : 0))*visual.intensity:0;}
  if(cameraTarget.current&&controls.current){const destination=cameraTarget.current;camera.position.lerp(destination.position,1-Math.exp(-dt*7));controls.current.target.lerp(destination.target,1-Math.exp(-dt*7));controls.current.update();if(camera.position.distanceTo(destination.position)<.01)cameraTarget.current=null;}
 });
 return <><group ref={root} scale={3}><group position={[-1.45,0,0]}><Engine/></group><mesh name="electrical-region" position={[.33,.06,0]}><cylinderGeometry args={[.11,.11,.15,24]}/><meshStandardMaterial color="#7c8587" metalness={.7} roughness={.3}/></mesh>
 {visuals.filter((v,i,a)=>focusCode?v.fault.code===focusCode:a.findIndex(x=>x.regions[0]===v.regions[0])===i).map(v=>{const b=bindings.find(x=>v.regions.some(r=>x.regions.includes(r)));if(!b)return null;const position=b.mesh.getWorldPosition(new Vector3()).divideScalar(3);return <Html key={v.fault.code} position={position.toArray()} center distanceFactor={3} zIndexRange={[8,1]}><button className="wt-mesh-label" style={{borderColor:v.color,color:v.color}} onClick={()=>choose(v.fault)}>{v.label}</button></Html>;})}
 </group><OrbitControls ref={controls} enablePan minDistance={.7} maxDistance={6} onStart={()=>cameraTarget.current=null}/></>;
}
export default function EngineFaultScene(props){const [reduced]=useState(()=>matchMedia('(prefers-reduced-motion: reduce)').matches);return <Canvas dpr={[1,1.5]} camera={{position:[2,1.5,2],fov:42}} gl={{antialias:true}}><color attach="background" args={['#edf1f4']}/><ambientLight intensity={1.5}/><directionalLight position={[3,5,2]} intensity={3}/><directionalLight position={[-2,1,-3]} intensity={2}/><Suspense fallback={null}><Assembly {...props} reduced={reduced}/></Suspense></Canvas>;}
