import { useLayoutEffect } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';
gsap.registerPlugin(ScrollTrigger);
export function useScrollController(track, motion, selected, publish) {
  useLayoutEffect(()=>{
    history.scrollRestoration='manual'; window.scrollTo(0,0);
    const lenis=new Lenis({ duration:0.9, smoothWheel:true });
    const tick=time=>lenis.raf(time*1000);
    lenis.on('scroll',ScrollTrigger.update); gsap.ticker.add(tick);
    return ()=>{ gsap.ticker.remove(tick);lenis.destroy(); };
  },[]);
  useLayoutEffect(()=>{
    const context=gsap.context(()=>{
      gsap.to(motion,{flight:1,ease:'none',scrollTrigger:{trigger:track.current,start:'top top',end:()=>`+=${window.innerHeight*2.8}`,scrub:0.65,onUpdate:publish},onUpdate:publish});
    });
    return ()=>context.revert();
  },[motion,track,publish]);
  useLayoutEffect(()=>{
    if(!selected) return;
    const context=gsap.context(()=>{
      gsap.to(motion,{zoom:1,ease:'none',scrollTrigger:{trigger:track.current,start:()=>`top+=${window.innerHeight*2.8} top`,end:()=>`+=${window.innerHeight*2.5}`,scrub:0.65},onUpdate:publish});
    });
    ScrollTrigger.refresh();
    return ()=>context.revert();
  },[selected,motion,track,publish]);
}
