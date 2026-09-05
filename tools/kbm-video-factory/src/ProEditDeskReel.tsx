import React from 'react';
import {AbsoluteFill, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {CinematicPolishedReel} from './CinematicPolishedReel';
import {Package13BrandLayer} from './Package13BrandLayer';
import {ProfessionalCaption} from './ProfessionalCaption';
import type {CinematicScene,KbmVideoProps} from './types';

const resolveSource=(src:string|null|undefined)=>{if(!src)return null;if(/^(https?:|data:|file:)/i.test(src))return src;return staticFile(src.replace(/^\/+/,''));};

const sceneMotion=(scene:CinematicScene,frame:number):React.CSSProperties=>{
  const local=Math.max(0,frame-scene.from);const duration=Math.max(1,scene.to-scene.from);const p=Math.min(1,local/duration);
  if(scene.motion==='pan-left')return{transform:`scale(1.08) translateX(${-32*p}px)`};
  if(scene.motion==='pan-right')return{transform:`scale(1.08) translateX(${32*p}px)`};
  if(scene.motion==='slow-push')return{transform:`scale(${1.015+.065*p})`};
  if(scene.motion==='punch')return{transform:`scale(${1.10-.055*p})`};
  return{};
};

const sceneEntrance=(scene:CinematicScene,frame:number,fps:number):React.CSSProperties=>{
  const local=Math.max(0,frame-scene.from);const window=Math.max(5,Math.min(Math.round(fps*.28),Math.floor((scene.to-scene.from)/3)));
  const p=interpolate(local,[0,window],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});const kind=scene.transitionIn??'fade';
  if(kind==='push')return{opacity:p,clipPath:`inset(0 ${100-p*100}% 0 0)`};
  if(kind==='wipe')return{opacity:p,clipPath:`polygon(0 0,${p*100}% 0,${Math.min(100,p*100+12)}% 100%,0 100%)`};
  if(kind==='cross-zoom')return{opacity:p,transform:`scale(${1.14-.14*p})`};
  if(kind==='flash')return{opacity:p,filter:`brightness(${1.85-.85*p}) contrast(${1.18-.08*p})`};
  if(kind==='hard')return{opacity:1};
  return{opacity:p};
};

export const ProEditDeskReel:React.FC<KbmVideoProps>=(props)=>{
  const frame=useCurrentFrame();const {fps}=useVideoConfig();const scenes=props.scenes??[];const assets=props.assets??[];const assetMap=new Map(assets.map((asset)=>[asset.id,asset]));const accent=props.accent??'#F4B400';const profile=props.captionProfile;
  return <AbsoluteFill>
    <CinematicPolishedReel {...props} captions={[]}/>
    {scenes.map((scene)=>{const asset=scene.assetId?assetMap.get(scene.assetId):undefined;const src=asset?.kind==='video'?resolveSource(asset.src):null;if(!src)return null;const intensity=Math.max(0,Math.min(1,scene.intensity??.55));return <Sequence key={scene.id} from={scene.from} durationInFrames={Math.max(1,scene.to-scene.from)}><AbsoluteFill style={{background:'#06121f',overflow:'hidden',...sceneEntrance(scene,frame,fps)}}><AbsoluteFill style={sceneMotion(scene,frame)}><OffthreadVideo src={src} muted style={{width:'100%',height:'100%',objectFit:'cover',filter:`contrast(${1.06+.07*intensity}) saturate(${1.02+.10*intensity}) brightness(${.96+.03*intensity})`}}/></AbsoluteFill><AbsoluteFill style={{background:'linear-gradient(180deg,rgba(3,12,22,.08),rgba(3,12,22,.01) 46%,rgba(3,12,22,.48))'}}/><AbsoluteFill style={{boxShadow:`inset 0 0 ${110+90*intensity}px rgba(0,0,0,${.22+.18*intensity})`}}/>{intensity>.80?<AbsoluteFill style={{background:`radial-gradient(circle at 74% 30%,rgba(244,180,0,${.06+.05*intensity}),transparent 38%)`,mixBlendMode:'screen'}}/>:null}</AbsoluteFill></Sequence>;})}
    {profile?<ProfessionalCaption captions={props.captions??[]} scenes={scenes} profile={profile} accent={accent}/>:null}
    <Package13BrandLayer {...props}/>
  </AbsoluteFill>;
};
