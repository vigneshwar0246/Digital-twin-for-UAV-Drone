export const ENGINE_COMPONENTS = ['crankshaft','cylinders','pistons','injector','oil-system','sensors'];
export default function Engine(){
 return <group name="piston-engine" position={[1.45,0,0]} scale={0.36}>
  <mesh name="crankshaft"><boxGeometry args={[1.25,0.65,0.62]}/><meshStandardMaterial color="#525b60" metalness={0.8} roughness={0.29}/></mesh>
  {[-1,1].map(side=>[0,1].map(i=><group name={`cylinders-${side}-${i}`} key={`${side}${i}`} position={[-0.32+i*0.66,0.06,side*0.5]} rotation={[Math.PI/2,0,0]}>
    <mesh name={`pistons-${side}-${i}`}><cylinderGeometry args={[0.235,0.235,0.68,24]}/><meshStandardMaterial color="#8c979b" metalness={0.85} roughness={0.27}/></mesh>
    {Array.from({length:8},(_,j)=><mesh key={j} position={[0,-0.29+j*0.082,0]}><cylinderGeometry args={[0.3,0.3,0.028,24]}/><meshStandardMaterial color="#a1aaa9" metalness={0.8} roughness={0.36}/></mesh>)}
    <mesh name="injector" position={[0,side*0.4,0]}><cylinderGeometry args={[0.06,0.07,0.2,12]}/><meshStandardMaterial color="#ed6b2f" metalness={0.6} roughness={0.3}/></mesh>
  </group>))}
  <mesh position={[0,-0.48,0]} name="oil-system"><boxGeometry args={[0.9,0.26,0.48]}/><meshStandardMaterial color="#343c40" metalness={0.7} roughness={0.3}/></mesh>
  <mesh position={[0,0.42,0]}><boxGeometry args={[0.9,0.14,0.43]}/><meshStandardMaterial color="#d6d5c9" metalness={0.75} roughness={0.3}/></mesh>
  <mesh name="sensors" position={[-0.43,0.48,0.18]}><boxGeometry args={[0.15,0.12,0.12]}/><meshStandardMaterial color="#ed6b2f"/></mesh>
  <mesh position={[0.78,0,0]} rotation={[0,0,Math.PI/2]}><cylinderGeometry args={[0.29,0.29,0.26,32]}/><meshStandardMaterial color="#7c8587" metalness={0.85} roughness={0.25}/></mesh>
 </group>;
}
