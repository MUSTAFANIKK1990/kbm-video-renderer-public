import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {KbmVideoProps} from './types';

const resolveSource=(src:string|null|undefined)=>{if(!src)return null;if(/^(https?:|data:|file:)/i.test(src))return src;return staticFile(src.replace(/^\/+/,''));};

export const Package13BrandLayer:React.FC<KbmVideoProps>=(props)=>{
  const frame=useCurrentFrame();
  const {fps,durationInFrames}=useVideoConfig();
  const brand=props.brand;
  const logoId=brand?.logoAssetId??'kbm-brand-logo';
  const logo=props.assets?.find((asset)=>asset.id===logoId&&asset.kind==='image');
  const src=resolveSource(logo?.src??brand?.logoSrc);
  if(!src)return null;
  const scene=props.scenes?.find((item)=>frame>=item.from&&frame<item.to);
  const strong=brand?.prominence==='strong'||brand?.persistentBug===true||brand?.endCardRequired===true;
  const forcedEndStart=Math.max(0,durationInFrames-Math.round(fps*(strong?2.35:1.7)));
  const isEnd=scene?.kind==='end-card'||scene?.beatRole==='cta'||(brand?.endCardRequired===true&&frame>=forcedEndStart);
  const revealFrames=Math.round(fps*1.25);
  const reveal=spring({frame:Math.min(frame,revealFrames),fps,config:{damping:16,stiffness:120,mass:.75}});
  const revealOpacity=interpolate(frame,[0,Math.round(fps*.12),revealFrames],[0,1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const watermarkOpacity=interpolate(frame,[Math.round(fps*.55),Math.round(fps*.9)],[0,strong?1:.96],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const cta=(props.cta??'گزینه‌ها را در کاریاب ماشین ببین').trim();
  return <AbsoluteFill style={{pointerEvents:'none'}}>
    {brand?.logoReveal!==false&&frame<revealFrames?<AbsoluteFill style={{alignItems:'center',justifyContent:'center',background:'radial-gradient(circle at center,rgba(11,31,51,.38),rgba(2,8,14,.08) 55%,transparent 75%)',opacity:revealOpacity}}><div style={{transform:`scale(${.78+.22*reveal})`,filter:'drop-shadow(0 18px 42px rgba(0,0,0,.52))'}}><Img src={src} style={{width:strong?430:360,maxHeight:strong?245:210,objectFit:'contain'}}/></div></AbsoluteFill>:null}
    {brand?.watermark!==false&&!isEnd?<div style={{position:'absolute',top:strong?118:150,right:strong?44:58,opacity:watermarkOpacity,filter:'drop-shadow(0 7px 18px rgba(0,0,0,.52))',zIndex:70}}><div style={{padding:strong?'11px 15px':'8px 11px',borderRadius:strong?20:18,background:strong?'rgba(4,17,29,.78)':'rgba(4,17,29,.58)',border:`${strong?2:1}px solid rgba(244,180,0,${strong ? .68 : .40})`,backdropFilter:'blur(10px)'}}><Img src={src} style={{height:strong?78:62,width:strong?238:190,objectFit:'contain'}}/></div></div>:null}
    {isEnd&&brand?.endCard!==false?<AbsoluteFill style={{alignItems:'center',justifyContent:'center',padding:'150px 78px 210px',background:'radial-gradient(circle at 50% 38%,rgba(244,180,0,.24),rgba(11,31,51,.72) 38%,rgba(3,10,18,.95) 82%)',zIndex:90}}><div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:strong?26:24,transform:`scale(${.92+.08*reveal})`,width:'100%'}}><Img src={src} style={{width:strong?540:440,maxHeight:strong?300:250,objectFit:'contain',filter:'drop-shadow(0 20px 55px rgba(0,0,0,.55))'}}/><div style={{fontSize:strong?36:30,fontWeight:900,color:'#F4B400',letterSpacing:2.4,direction:'ltr'}}>{brand?.site??'KARYABMASHIN.IR'}</div><div style={{maxWidth:860,padding:strong?'18px 30px 20px':'14px 24px 16px',borderRadius:22,background:'#F4B400',color:'#0B1F33',fontSize:strong?42:34,lineHeight:1.45,fontWeight:950,textAlign:'center',direction:'rtl',boxShadow:'0 18px 46px rgba(0,0,0,.34)'}}>{cta}</div></div></AbsoluteFill>:null}
  </AbsoluteFill>;
};
