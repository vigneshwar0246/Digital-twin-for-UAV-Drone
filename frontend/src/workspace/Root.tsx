import {lazy,Suspense,useEffect,useState,Component,type ReactNode} from 'react';
const Intro=lazy(()=>import('../App.jsx'));
const Workspace=lazy(()=>import('./Workspace'));
export function navigate(path:string){history.pushState({},'',path);window.dispatchEvent(new PopStateEvent('popstate'));window.scrollTo(0,0);}
class Boundary extends Component<{children:ReactNode},{error:boolean}>{state={error:false};static getDerivedStateFromError(){return {error:true};}render(){return this.state.error?<div style={{padding:40}}>The workspace could not render. <button onClick={()=>location.reload()}>Reload</button></div>:this.props.children;}}
export default function Root(){const [path,setPath]=useState(location.pathname);useEffect(()=>{const route=()=>setPath(location.pathname);const enter=()=>navigate('/twin');window.addEventListener('popstate',route);window.addEventListener('aerion:enter',enter);return()=>{window.removeEventListener('popstate',route);window.removeEventListener('aerion:enter',enter);};},[]);return <Boundary><Suspense fallback={<div style={{padding:40}}>Initializing AERO-TWIN…</div>}>{path==='/'?<Intro/>:<Workspace path={path}/>}</Suspense></Boundary>;}
