import React from 'react';
import {AbsoluteFill, Audio, Img, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {KbmVideoProps} from './types';

const resolveSource=(src:string|null|undefined)=>{if(!src)return null;if(/^(https?:|data:|file:)/i.test(src))return src;return staticFile(src.replace(/^\/+/,''));};

export const CriticPolishReel:React.FC<KbmVideoProps>=(props)=>{
  const frame=useCurrentFrame();
  const config=useVideoConfig();
  const fps=config.fps;
  const effectiveDurationInFrames=Math.max(1,Number(props.durationInFrames??config.durationInFrames));
  const source=resolveSource(props.media);
  const narrationSource=resolveSource(props.narration);
  const brandLogo=resolveSource(props.brand?.logoSrc);
  const brandName=props.brand?.name??'کاریاب ماشین';
  const brandSite=props.brand?.site??'KARYABMASHIN.IR';
  const profile=props.captionProfile;
  const captions=props.captions??[];
  const caption=captions.find((item)=>frame>=item.from&&frame<=item.to);
  const safeBottom=Math.max(340,Number(profile?.bottom??360));
  const captionBottom=Math.max(500,safeBottom);
  const fontSize=Math.max(48,Number(profile?.fontSize??56));
  const hookFrames=Math.min(effectiveDurationInFrames,Math.round(fps*1.95));
  const isHook=frame<hookFrames;
  const endStart=Math.max(0,effectiveDurationInFrames-Math.round(fps*3.0));
  const preCtaStart=Math.max(0,endStart-Math.round(fps*.55));
  const isEnd=frame>=endStart;
  const showPreCta=frame>=preCtaStart&&frame<endStart;
  const accent=props.accent??'#F4B400';
  const narrationVolume=Math.max(0,Math.min(1,Number(props.narrationVolume??1)));

  return <AbsoluteFill style={{background:props.background??'#0B1F33',fontFamily:'Estedad, Noto Sans Arabic, Arial, sans-serif',direction:'rtl',overflow:'hidden'}}>
    {source&&!isEnd?<AbsoluteFill>
      <OffthreadVideo src={source} muted={true} volume={0} style={{width:'100%',height:'100%',objectFit:'cover'}}/>
    </AbsoluteFill>:null}

    {narrationSource?<Audio src={narrationSource} volume={narrationVolume}/>:null}

    {!isEnd?<AbsoluteFill style={{background:'linear-gradient(180deg,transparent 0%,transparent 70%,rgba(3,10,18,.14) 76%,rgba(3,10,18,.58) 100%)',pointerEvents:'none'}}/>:null}

    {caption&&!isEnd?<div style={{position:'absolute',left:0,right:0,bottom:215,height:720,zIndex:44,pointerEvents:'none',background:'linear-gradient(180deg,rgba(3,10,18,0) 0%,rgba(3,10,18,.22) 14%,rgba(3,10,18,.76) 39%,rgba(3,10,18,.96) 66%,#030A12 100%)'}}/>:null}

    {!isEnd?<div style={{position:'absolute',top:92,left:52,zIndex:76,direction:'ltr',display:'flex',alignItems:'center',gap:14,padding:'10px 15px 11px 12px',borderRadius:18,background:'rgba(4,17,29,.90)',border:`2px solid rgba(244,180,0,.82)`,boxShadow:'0 12px 32px rgba(0,0,0,.40)'}}>
      {brandLogo?<Img src={brandLogo} style={{width:78,height:82,objectFit:'contain',filter:'drop-shadow(0 7px 12px rgba(0,0,0,.42))'}}/>:null}
      <div style={{display:'flex',flexDirection:'column',gap:2,alignItems:'flex-start'}}>
        <span style={{color:'#fff',fontSize:28,fontWeight:950,direction:'rtl',lineHeight:1.1}}>{brandName}</span>
        <span style={{color:accent,fontSize:24,fontWeight:950,letterSpacing:1.1,direction:'ltr'}}>{brandSite}</span>
      </div>
    </div>:null}

    {caption&&!isEnd&&!showPreCta?<div style={{position:'absolute',left:70,right:70,bottom:captionBottom,display:'flex',justifyContent:'center',zIndex:60}}>
      <div style={{maxWidth:860,padding:isHook?'25px 32px 27px':'20px 30px 22px',borderRadius:22,background:'rgba(3,14,25,.99)',border:`3px solid rgba(244,180,0,${isHook ? .92 : .78})`,boxShadow:'0 20px 62px rgba(0,0,0,.64)',textAlign:'center',fontSize:isHook?Math.max(60,Number(profile?.hookFontSize??66)):fontSize,lineHeight:1.34,fontWeight:950,color:'#fff',textShadow:'0 3px 12px rgba(0,0,0,.9)'}}>
        {caption.text}
      </div>
    </div>:null}

    {showPreCta?<div style={{position:'absolute',left:78,right:78,bottom:390,zIndex:90,display:'flex',justifyContent:'center'}}>
      <div style={{padding:'17px 25px 19px',borderRadius:18,background:'rgba(3,14,25,.97)',border:`2px solid ${accent}`,boxShadow:'0 18px 52px rgba(0,0,0,.5)',textAlign:'center',fontSize:42,lineHeight:1.35,fontWeight:950,color:'#fff'}}>
        گزینه‌ها را در <span style={{color:accent,direction:'ltr'}}>{brandSite}</span> ببین
      </div>
    </div>:null}

    {isEnd?<AbsoluteFill style={{zIndex:100,alignItems:'center',justifyContent:'center',padding:'116px 72px 160px',background:'radial-gradient(circle at 50% 29%,rgba(244,180,0,.20),rgba(11,31,51,.97) 46%,#030A12 100%)'}}>
      <div style={{width:'100%',display:'flex',flexDirection:'column',alignItems:'center',textAlign:'center',gap:16}}>
        {brandLogo?<Img src={brandLogo} style={{width:205,height:218,objectFit:'contain',filter:`drop-shadow(0 16px 34px rgba(0,0,0,.48)) drop-shadow(0 0 16px rgba(244,180,0,.16))`}}/>:null}
        <div style={{fontSize:60,lineHeight:1.15,fontWeight:950,color:'#fff',textShadow:'0 12px 34px rgba(0,0,0,.52)'}}>{brandName}</div>
        <div style={{width:124,height:5,borderRadius:999,background:accent,boxShadow:`0 0 22px ${accent}`}}/>
        <div style={{maxWidth:900,fontSize:47,lineHeight:1.38,fontWeight:950,color:'#fff'}}>ماشین‌آلات را ببین و مقایسه کن</div>
        <div style={{marginTop:2,padding:'17px 31px 19px',borderRadius:18,background:accent,color:'#0B1F33',fontSize:41,lineHeight:1.15,fontWeight:950,boxShadow:'0 18px 45px rgba(0,0,0,.38)'}}>مشاهده در کاریاب ماشین</div>
        <div style={{fontSize:44,lineHeight:1.15,fontWeight:950,color:accent,letterSpacing:1.5,direction:'ltr'}}>{brandSite}</div>
      </div>
    </AbsoluteFill>:null}
  </AbsoluteFill>;
};
