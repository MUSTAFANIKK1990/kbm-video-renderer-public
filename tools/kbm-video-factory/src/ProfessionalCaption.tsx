import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import type {CaptionCue, CaptionProfile, CinematicScene} from './types';
const WordLine: React.FC<{cue: CaptionCue; frame: number; accent: string; activeScale: number}> = ({cue,frame,accent,activeScale}) => {
  if (!cue.words?.length) return <>{cue.text}</>;
  return <span style={{display:'inline-flex',flexWrap:'wrap',justifyContent:'center',gap:'0 13px'}}>{cue.words.map((word,index)=>{const active=frame>=word.from&&frame<=word.to; return <span key={`${word.from}-${index}`} style={{color:active?accent:'#fff',transform:active?`scale(${activeScale}) translateY(-2px)`:'scale(1)',textShadow:active?`0 0 24px ${accent}`:undefined}}>{word.text}</span>;})}</span>;
};
export const ProfessionalCaption: React.FC<{captions:CaptionCue[];scenes:CinematicScene[];profile:CaptionProfile;accent:string}> = ({captions,scenes,profile,accent}) => {
  const frame=useCurrentFrame(); const {fps}=useVideoConfig(); const cue=captions.find((item)=>frame>=item.from&&frame<=item.to); const scene=scenes.find((item)=>frame>=item.from&&frame<item.to); if(!cue||scene?.suppressCaption)return null;
  const hook=frame<fps*2.6; const desired=hook?profile.hookFontSize:profile.fontSize; const size=Math.max(profile.minFontSize,Math.min(profile.maxFontSize,desired-Math.max(0,cue.text.length-34)*0.45)); const local=Math.max(0,frame-cue.from); const opacity=interpolate(local,[0,Math.max(3,fps*0.08)],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  return <div style={{position:'absolute',left:72,right:72,bottom:profile.bottom,display:'flex',justifyContent:'center',zIndex:50,opacity,direction:'rtl',pointerEvents:'none'}}><div style={{maxWidth:930,padding:profile.pill?'15px 24px 18px':'8px 12px 12px',borderRadius:profile.pill?24:0,background:profile.pill?'rgba(3,13,23,.72)':'transparent',backdropFilter:profile.pill?'blur(8px)':undefined,color:'#fff',fontSize:size,lineHeight:1.34,fontWeight:950,textAlign:'center',WebkitTextStroke:`${profile.outlinePx}px rgba(7,23,39,.94)`,paintOrder:'stroke fill',textShadow:'0 8px 28px rgba(0,0,0,.72)',fontFamily:'Estedad, Noto Sans Arabic, Arial, sans-serif'}}><WordLine cue={cue} frame={frame} accent={accent} activeScale={profile.activeScale}/></div></div>;
};
