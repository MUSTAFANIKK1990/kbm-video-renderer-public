import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {KbmVideoProps} from './types';

const resolveSource=(src:string|null|undefined)=>{if(!src)return null;if(/^(https?:|data:|file:)/i.test(src))return src;return staticFile(src.replace(/^\/+/,''));};
const clamp=(value:number,min=0,max=1)=>Math.max(min,Math.min(max,value));

export const CinematicWebsiteReel:React.FC<KbmVideoProps>=(props)=>{
  const frame=useCurrentFrame();
  const {fps,durationInFrames}=useVideoConfig();
  const total=Math.max(1,Number(props.durationInFrames??durationInFrames));
  const source=resolveSource(props.media);
  const narration=resolveSource(props.narration);
  const logo=resolveSource(props.brand?.logoSrc);
  const websiteAsset=(props.assets??[]).find((asset)=>asset.id==='website-walkthrough');
  const website=resolveSource(websiteAsset?.src);
  const accent=props.accent??'#F4B400';
  const navy=props.background??'#071827';
  const brandName=props.brand?.name??'کاریاب ماشین';
  const brandSite=props.brand?.site??'KARYABMASHIN.IR';

  // Final rc7 polish: skip the weak source lead-in, hold machine imagery longer,
  // compress the complete 9s first-party site walkthrough, then give CTA 5.8s.
  const footageEnd=Math.round(fps*8.50);
  const websiteEnd=Math.round(fps*14.20);
  const endStart=websiteEnd;
  const websitePlaybackRate=1.60;
  const isFootage=frame<footageEnd;
  const isWebsite=frame>=footageEnd&&frame<websiteEnd;
  const isEnd=frame>=endStart;
  const localWebsite=Math.max(0,frame-footageEnd);
  const localEnd=Math.max(0,frame-endStart);

  const shotCuts=[0,Math.round(fps*1.45),Math.round(fps*3.15),Math.round(fps*5.40),footageEnd];
  const shotIndex=frame<shotCuts[1]?0:frame<shotCuts[2]?1:frame<shotCuts[3]?2:3;
  const shotLocal=Math.max(0,frame-shotCuts[shotIndex]);
  const shotLength=Math.max(1,shotCuts[shotIndex+1]-shotCuts[shotIndex]);
  const shotBaseScale=[1.32,1.09,1.30,1.16][shotIndex];
  const shotX=[-4.0,2.0,-4.5,1.4][shotIndex];
  const shotY=[-1.0,-1.4,1.0,-2.0][shotIndex];
  const shotMicroZoom=interpolate(shotLocal,[0,shotLength],[0,0.042],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const cutFlash=interpolate(shotLocal,[0,4],[0.18,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});

  const cues=[
    {from:0,to:Math.round(fps*1.55),text:'ماشینت هنوز اجاره نرفته؟',accent:'اجاره نرفته؟'},
    {from:Math.round(fps*1.55),to:Math.round(fps*3.35),text:'از آگهی بی‌نتیجه خسته شدی؟',accent:'خسته شدی؟'},
    {from:Math.round(fps*3.35),to:Math.round(fps*5.45),text:'وقتشه بیشتر دیده بشی!',accent:'بیشتر دیده بشی!'},
    {from:Math.round(fps*5.45),to:footageEnd-1,text:'کاریاب ماشین؛ بازار تخصصی ماشین‌آلات',accent:'کاریاب ماشین'},
    {from:footageEnd,to:Math.round(fps*10.25),text:'وارد کاریاب ماشین شو',accent:'کاریاب ماشین'},
    {from:Math.round(fps*10.25),to:Math.round(fps*12.10),text:'آگهی ماشینت رو ثبت کن',accent:'ثبت کن'},
    {from:Math.round(fps*12.10),to:websiteEnd-1,text:'مستقیم‌تر به متقاضی برس',accent:'متقاضی'},
  ];
  const cue=cues.find((item)=>frame>=item.from&&frame<=item.to);
  const cueProgress=cue?clamp((frame-cue.from)/Math.max(1,Math.min(8,cue.to-cue.from))):0;
  const cueScale=cue?interpolate(cueProgress,[0,1],[0.92,1],{easing:Easing.out(Easing.cubic),extrapolateLeft:'clamp',extrapolateRight:'clamp'}):1;
  const cueOpacity=cue?interpolate(cueProgress,[0,1],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}):0;
  const websiteScale=interpolate(localWebsite,[0,Math.max(1,websiteEnd-footageEnd)],[1.015,1.055],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const websiteDrift=interpolate(localWebsite,[0,Math.max(1,websiteEnd-footageEnd)],[-0.5,0.5],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const endLift=interpolate(localEnd,[0,16],[36,0],{easing:Easing.out(Easing.cubic),extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const endOpacity=interpolate(localEnd,[0,10],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const ctaPulse=1+Math.sin(localEnd/9)*0.014;
  const sweep=interpolate(frame,[footageEnd-8,footageEnd+10],[-25,118],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const endSweep=interpolate(frame,[endStart-7,endStart+12],[-25,118],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});

  return <AbsoluteFill style={{background:navy,fontFamily:'Estedad, Noto Sans Arabic, Arial, sans-serif',direction:'rtl',overflow:'hidden'}}>
    {narration?<Audio src={narration} volume={Math.max(0,Number(props.narrationVolume??1))}/>:null}
    <Audio src={staticFile('rc7-bed.wav')} volume={0.14}/>
    <Sequence from={0}><Audio src={staticFile('rc7-impact.wav')} volume={0.22}/></Sequence>
    <Sequence from={Math.round(fps*1.45)}><Audio src={staticFile('rc7-whoosh.wav')} volume={0.14}/></Sequence>
    <Sequence from={Math.round(fps*3.15)}><Audio src={staticFile('rc7-whoosh.wav')} volume={0.13}/></Sequence>
    <Sequence from={Math.round(fps*5.35)}><Audio src={staticFile('rc7-click.wav')} volume={0.16}/></Sequence>
    <Sequence from={footageEnd-4}><Audio src={staticFile('rc7-whoosh.wav')} volume={0.20}/></Sequence>
    <Sequence from={footageEnd+8}><Audio src={staticFile('rc7-click.wav')} volume={0.19}/></Sequence>
    <Sequence from={Math.round(fps*11.95)}><Audio src={staticFile('rc7-click.wav')} volume={0.15}/></Sequence>
    <Sequence from={endStart}><Audio src={staticFile('rc7-impact.wav')} volume={0.20}/></Sequence>

    {source&&isFootage?<AbsoluteFill style={{transform:`translate(${shotX}%,${shotY}%) scale(${shotBaseScale+shotMicroZoom})`,filter:'contrast(1.15) saturate(1.10) brightness(1.04)'}}>
      <OffthreadVideo src={source} startFrom={Math.round(fps*1.0)} muted={true} volume={0} style={{width:'100%',height:'100%',objectFit:'cover'}}/>
    </AbsoluteFill>:null}

    {isFootage?<>
      <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(3,10,18,.42) 0%,rgba(3,10,18,.01) 25%,rgba(3,10,18,.04) 52%,rgba(3,10,18,.82) 70%,#030A12 100%)'}}/>
      <AbsoluteFill style={{background:`rgba(244,180,0,${cutFlash})`,mixBlendMode:'screen'}}/>
      <div style={{position:'absolute',left:0,right:0,top:0,height:198,zIndex:50,background:'linear-gradient(180deg,#061522 0%,rgba(6,21,34,.98) 72%,rgba(6,21,34,.80) 100%)',boxShadow:'0 18px 45px rgba(0,0,0,.25)'}}/>
      <div style={{position:'absolute',left:0,right:0,bottom:0,height:820,zIndex:50,background:'linear-gradient(180deg,rgba(3,10,18,0) 0%,rgba(3,10,18,.88) 18%,#030A12 36%,#030A12 100%)'}}/>
    </>:null}

    {!isEnd?<div style={{position:'absolute',top:46,left:54,right:54,zIndex:80,display:'flex',alignItems:'center',justifyContent:'flex-start',direction:'ltr'}}>
      <div style={{display:'flex',alignItems:'center',gap:13,padding:'8px 14px 9px 10px',borderRadius:16,border:`1.7px solid ${accent}`,background:'rgba(4,17,29,.96)',boxShadow:'0 12px 32px rgba(0,0,0,.38)'}}>
        {logo?<Img src={logo} style={{width:63,height:66,objectFit:'contain'}}/>:null}
        <div style={{display:'flex',flexDirection:'column',alignItems:'flex-start',gap:0}}>
          <span style={{fontSize:27,fontWeight:950,color:'#fff',direction:'rtl'}}>{brandName}</span>
          <span style={{fontSize:21,fontWeight:900,color:accent,direction:'ltr',letterSpacing:1}}>{brandSite}</span>
        </div>
      </div>
    </div>:null}

    {website&&isWebsite?<AbsoluteFill style={{zIndex:30,background:'radial-gradient(circle at 50% 35%,rgba(244,180,0,.18),rgba(4,15,25,.97) 52%,#02070d 100%)'}}>
      <div style={{position:'absolute',left:54,right:54,top:154,bottom:146,borderRadius:34,overflow:'hidden',background:'#fff',border:'2px solid rgba(244,180,0,.66)',boxShadow:'0 38px 100px rgba(0,0,0,.64)',transform:`translateX(${websiteDrift}%) scale(${websiteScale})`}}>
        <div style={{height:74,display:'flex',alignItems:'center',gap:12,padding:'0 20px',direction:'ltr',background:'#081522',borderBottom:'1px solid rgba(255,255,255,.12)'}}>
          <div style={{display:'flex',gap:7}}><span style={{width:12,height:12,borderRadius:99,background:'#ff5f57'}}/><span style={{width:12,height:12,borderRadius:99,background:'#febc2e'}}/><span style={{width:12,height:12,borderRadius:99,background:'#28c840'}}/></div>
          <div style={{flex:1,height:43,borderRadius:12,background:'rgba(255,255,255,.10)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:21,fontWeight:900,color:'#fff',direction:'ltr'}}>karyabmashin.ir</div>
        </div>
        <div style={{position:'absolute',left:0,right:0,top:74,bottom:0,overflow:'hidden'}}>
          <OffthreadVideo src={website} playbackRate={websitePlaybackRate} muted={true} volume={0} style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:'top center'}}/>
        </div>
      </div>
      <div style={{position:'absolute',right:74,top:118,zIndex:70,padding:'9px 15px',borderRadius:99,background:accent,color:'#081522',fontSize:19,fontWeight:950}}>نمای واقعی سایت</div>
      <div style={{position:'absolute',left:0,right:0,bottom:0,height:500,background:'linear-gradient(180deg,rgba(2,7,13,0),rgba(2,7,13,.92) 42%,#02070d 100%)'}}/>
      {localWebsite>10&&localWebsite<55?<div style={{position:'absolute',right:115,top:315,zIndex:65,width:66,height:66,borderRadius:99,border:`4px solid ${accent}`,boxShadow:`0 0 0 ${10+Math.sin(localWebsite/3)*5}px rgba(244,180,0,.16)`,background:'rgba(255,255,255,.12)'}}/>:null}
    </AbsoluteFill>:null}

    {cue&&!isEnd?<div style={{position:'absolute',left:54,right:54,bottom:isWebsite?228:330,zIndex:95,display:'flex',justifyContent:'center',opacity:cueOpacity,transform:`scale(${cueScale}) translateY(${(1-cueProgress)*12}px)`}}>
      <div style={{maxWidth:960,padding:'20px 32px 24px',borderRadius:23,background:'#020B13',border:`3px solid ${accent}`,boxShadow:'0 26px 80px rgba(0,0,0,.86)',fontSize:frame<70?64:56,lineHeight:1.28,fontWeight:950,color:'#fff',textAlign:'center',textShadow:'0 2px 8px rgba(0,0,0,.72)'}}>
        {cue.text.split(cue.accent).map((part,index,arr)=><React.Fragment key={`${cue.from}-${index}`}>{part}{index<arr.length-1?<span style={{color:accent,textShadow:'0 2px 6px rgba(0,0,0,.85)'}}>{cue.accent}</span>:null}</React.Fragment>)}
      </div>
    </div>:null}

    {frame>=footageEnd-8&&frame<=footageEnd+10?<div style={{position:'absolute',zIndex:120,top:0,bottom:0,left:`${sweep}%`,width:'14%',transform:'skewX(-10deg)',background:'linear-gradient(90deg,rgba(244,180,0,0),rgba(244,180,0,.92),rgba(255,255,255,.95),rgba(244,180,0,0))',filter:'blur(2px)',boxShadow:'0 0 70px rgba(244,180,0,.55)'}}/>:null}
    {frame>=endStart-7&&frame<=endStart+12?<div style={{position:'absolute',zIndex:165,top:0,bottom:0,left:`${endSweep}%`,width:'13%',transform:'skewX(-11deg)',background:'linear-gradient(90deg,rgba(244,180,0,0),rgba(244,180,0,.88),rgba(255,255,255,.92),rgba(244,180,0,0))',filter:'blur(2px)'}}/>:null}

    {isEnd?<AbsoluteFill style={{zIndex:150,alignItems:'center',justifyContent:'center',padding:'80px 64px 122px',background:'radial-gradient(circle at 50% 25%,rgba(244,180,0,.28),rgba(7,24,39,.98) 45%,#02070d 100%)'}}>
      <div style={{width:'100%',display:'flex',flexDirection:'column',alignItems:'center',gap:14,textAlign:'center',opacity:endOpacity,transform:`translateY(${endLift}px)`}}>
        {logo?<Img src={logo} style={{width:170,height:178,objectFit:'contain',filter:'drop-shadow(0 18px 38px rgba(0,0,0,.52))'}}/>:null}
        <div style={{fontSize:46,fontWeight:950,color:'#fff',lineHeight:1.12}}>{brandName}</div>
        <div style={{width:130,height:6,borderRadius:99,background:accent,boxShadow:`0 0 26px ${accent}`}}/>
        <div style={{maxWidth:930,fontSize:58,fontWeight:950,lineHeight:1.25,color:'#fff'}}>ماشینت را همین حالا آگهی کن</div>
        <div style={{width:'92%',marginTop:2,padding:'20px 24px 22px',borderRadius:22,border:`3px solid ${accent}`,background:'rgba(2,11,19,.78)',fontSize:66,fontWeight:950,color:accent,direction:'ltr',letterSpacing:1.8,boxShadow:'0 22px 60px rgba(0,0,0,.46)'}}>{brandSite}</div>
        <div style={{marginTop:4,padding:'20px 40px 23px',borderRadius:20,background:accent,color:'#081522',fontSize:45,fontWeight:950,boxShadow:'0 20px 52px rgba(0,0,0,.42)',transform:`scale(${ctaPulse})`}}>ورود و ثبت آگهی</div>
        <div style={{fontSize:25,fontWeight:900,color:'rgba(255,255,255,.84)'}}>همین حالا وارد سایت شو</div>
      </div>
    </AbsoluteFill>:null}
  </AbsoluteFill>;
};
