import React from 'react';
import {AbsoluteFill,Audio,Easing,Img,OffthreadVideo,Sequence,interpolate,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';
import type {CampVertical,KbmVideoProps} from './types';

const resolveSource=(src:string|null|undefined)=>{if(!src)return null;if(/^(https?:|data:|file:)/i.test(src))return src;return staticFile(src.replace(/^\/+/,''));};
const clamp=(value:number,min=0,max=1)=>Math.max(min,Math.min(max,value));

type CopySet={hook:string;pain:string;solution:string;proof:string;website:string;cta:string;};
const copyFor=(vertical:CampVertical|undefined,topic:string,cta:string|undefined):CopySet=>{
  const finalCta=(cta??'').trim();
  if(vertical==='machine-sale')return{
    hook:'ماشینت برای فروش آماده‌ست؟',
    pain:'هنوز خریدار واقعی پیدا نکردی؟',
    solution:'در کاریاب ماشین بیشتر دیده شو',
    proof:'بازار تخصصی خرید و فروش ماشین‌آلات',
    website:'آگهی‌ها را ببین، مقایسه کن و انتخاب کن',
    cta:finalCta||'همین حالا آگهی فروش را ثبت کن',
  };
  if(vertical==='rental')return{
    hook:'ماشینت آماده کاره؟',
    pain:'هنوز متقاضی مناسب پیدا نکردی؟',
    solution:'در کاریاب ماشین بیشتر دیده شو',
    proof:'بازار تخصصی اجاره ماشین‌آلات',
    website:'آگهی‌های واقعی را مستقیم بررسی کن',
    cta:finalCta||'همین حالا آگهی اجاره را ثبت کن',
  };
  if(vertical==='services')return{
    hook:'خدمت تخصصی ارائه می‌دی؟',
    pain:'مشتری مناسب سخت پیدا می‌شه؟',
    solution:'توان فنی‌ات را در کاریاب ماشین معرفی کن',
    proof:'بازار تخصصی خدمات ماشین‌آلات',
    website:'خدمات و متخصصان را مستقیم بررسی کن',
    cta:finalCta||'همین حالا خدمتت را ثبت کن',
  };
  const cleanTopic=topic.trim()||'ماشین‌آلات و خدمات پروژه';
  return{
    hook:'دنبال یک مسیر تخصصی‌تری؟',
    pain:`برای ${cleanTopic} انتخاب دقیق مهمه`,
    solution:'کاریاب ماشین؛ یک مسیر تخصصی برای بررسی و ارتباط',
    proof:'ماشین‌آلات، خدمات و فرصت‌های پروژه',
    website:'جزئیات واقعی را در سایت ببین',
    cta:finalCta||'همین حالا وارد کاریاب ماشین شو',
  };
};

export const CinematicAdMasterReel:React.FC<KbmVideoProps>=(props)=>{
  const frame=useCurrentFrame();
  const {fps,durationInFrames}=useVideoConfig();
  const total=Math.max(1,Number(props.durationInFrames??durationInFrames));
  const source=resolveSource(props.media);
  const narration=resolveSource(props.narration);
  const logo=resolveSource(props.brand?.logoSrc);
  const websiteAsset=(props.assets??[]).find((asset)=>asset.id==='website-walkthrough');
  const website=resolveSource(websiteAsset?.src);
  const camp=props.camp;
  const copy=copyFor(camp?.vertical,camp?.topic??'',props.cta);
  const accent=props.accent??'#F4B400';
  const navy=props.background??'#071827';
  const brandName=props.brand?.name??'کاریاب ماشین';
  const brandSite=props.brand?.site??'KARYABMASHIN.IR';

  const footageEnd=Math.max(Math.round(fps*6.8),Math.round(total*(website?0.42:0.66)));
  const websiteEnd=website?Math.max(footageEnd+Math.round(fps*4.5),Math.round(total*0.75)):footageEnd;
  const endStart=Math.min(total-Math.round(fps*2.5),websiteEnd);
  const isFootage=frame<footageEnd;
  const isWebsite=Boolean(website)&&frame>=footageEnd&&frame<endStart;
  const isEnd=frame>=endStart;
  const localEnd=Math.max(0,frame-endStart);
  const localWebsite=Math.max(0,frame-footageEnd);

  const shotCuts=[0,Math.round(footageEnd*.18),Math.round(footageEnd*.39),Math.round(footageEnd*.66),footageEnd];
  const shotIndex=frame<shotCuts[1]?0:frame<shotCuts[2]?1:frame<shotCuts[3]?2:3;
  const shotLocal=Math.max(0,frame-shotCuts[shotIndex]);
  const shotLength=Math.max(1,shotCuts[shotIndex+1]-shotCuts[shotIndex]);
  const baseScale=[1.34,1.12,1.29,1.17][shotIndex];
  const shiftX=[-4.5,2.4,-3.8,1.8][shotIndex];
  const shiftY=[-1.2,-1.8,1.4,-2.2][shotIndex];
  const micro=interpolate(shotLocal,[0,shotLength],[0,.046],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const flash=interpolate(shotLocal,[0,4],[.17,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});

  const cuePoints=[0,shotCuts[1],shotCuts[2],shotCuts[3],footageEnd,endStart];
  const cues=[
    {from:cuePoints[0],to:cuePoints[1]-1,text:copy.hook,accent:'؟'},
    {from:cuePoints[1],to:cuePoints[2]-1,text:copy.pain,accent:'واقعی'},
    {from:cuePoints[2],to:cuePoints[3]-1,text:copy.solution,accent:'کاریاب ماشین'},
    {from:cuePoints[3],to:cuePoints[4]-1,text:copy.proof,accent:'تخصصی'},
    ...(website?[{from:cuePoints[4],to:cuePoints[5]-1,text:copy.website,accent:'ببین'}]:[]),
  ];
  const cue=cues.find((item)=>frame>=item.from&&frame<=item.to);
  const cueProgress=cue?clamp((frame-cue.from)/Math.max(1,Math.min(9,cue.to-cue.from))):0;
  const cueOpacity=cue?interpolate(cueProgress,[0,1],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}):0;
  const cueScale=cue?interpolate(cueProgress,[0,1],[.91,1],{easing:Easing.out(Easing.cubic),extrapolateLeft:'clamp',extrapolateRight:'clamp'}):1;
  const siteSpan=Math.max(1,endStart-footageEnd);
  const websiteScale=interpolate(localWebsite,[0,siteSpan],[1.01,1.055],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const websiteDrift=interpolate(localWebsite,[0,siteSpan],[-.5,.6],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const endOpacity=interpolate(localEnd,[0,10],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const endLift=interpolate(localEnd,[0,18],[38,0],{easing:Easing.out(Easing.cubic),extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const ctaPulse=1+Math.sin(localEnd/9)*.013;
  const sweep=interpolate(frame,[footageEnd-8,footageEnd+10],[-25,118],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const endSweep=interpolate(frame,[endStart-7,endStart+12],[-25,118],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});

  const renderAccent=(text:string,needle:string)=>{
    if(!needle||!text.includes(needle))return text;
    const parts=text.split(needle);
    return <>{parts.map((part,index)=><React.Fragment key={`${needle}-${index}`}>{part}{index<parts.length-1?<span style={{color:accent}}>{needle}</span>:null}</React.Fragment>)}</>;
  };

  return <AbsoluteFill style={{background:navy,fontFamily:'Estedad, Noto Sans Arabic, Arial, sans-serif',direction:'rtl',overflow:'hidden'}}>
    {narration?<Audio src={narration} volume={Math.max(0,Number(props.narrationVolume??1))}/>:null}
    <Audio src={staticFile('rc7-bed.wav')} volume={0.14}/>
    <Sequence from={0}><Audio src={staticFile('rc7-impact.wav')} volume={0.22}/></Sequence>
    {shotCuts.slice(1,-1).map((cut,index)=><Sequence key={`cut-${cut}`} from={Math.max(0,cut-2)}><Audio src={staticFile(index%2===0?'rc7-whoosh.wav':'rc7-click.wav')} volume={index%2===0?.15:.13}/></Sequence>)}
    {website?<Sequence from={Math.max(0,footageEnd-3)}><Audio src={staticFile('rc7-whoosh.wav')} volume={0.20}/></Sequence>:null}
    <Sequence from={endStart}><Audio src={staticFile('rc7-impact.wav')} volume={0.20}/></Sequence>

    {source&&isFootage?<AbsoluteFill style={{transform:`translate(${shiftX}%,${shiftY}%) scale(${baseScale+micro})`,filter:'contrast(1.16) saturate(1.10) brightness(1.04)'}}>
      <OffthreadVideo src={source} startFrom={Math.round(fps*.8)} muted={true} volume={0} style={{width:'100%',height:'100%',objectFit:'cover'}}/>
    </AbsoluteFill>:null}

    {isFootage?<>
      <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(2,9,16,.43) 0%,rgba(2,9,16,.02) 28%,rgba(2,9,16,.05) 52%,rgba(2,9,16,.88) 80%,#02070d 100%)'}}/>
      <AbsoluteFill style={{background:`rgba(244,180,0,${flash})`,mixBlendMode:'screen'}}/>
      <div style={{position:'absolute',left:0,right:0,top:0,height:190,zIndex:50,background:'linear-gradient(180deg,#061522 0%,rgba(6,21,34,.97) 74%,rgba(6,21,34,.76) 100%)'}}/>
      <div style={{position:'absolute',left:0,right:0,bottom:0,height:760,zIndex:50,background:'linear-gradient(180deg,rgba(2,7,13,0),rgba(2,7,13,.87) 22%,#02070d 48%,#02070d 100%)'}}/>
    </>:null}

    {!isEnd?<div style={{position:'absolute',top:44,left:52,right:52,zIndex:90,display:'flex',justifyContent:'flex-start',direction:'ltr'}}>
      <div style={{display:'flex',alignItems:'center',gap:13,padding:'8px 14px 9px 10px',borderRadius:17,border:`1.8px solid ${accent}`,background:'rgba(4,17,29,.96)',boxShadow:'0 14px 34px rgba(0,0,0,.40)'}}>
        {logo?<Img src={logo} style={{width:62,height:65,objectFit:'contain'}}/>:null}
        <div style={{display:'flex',flexDirection:'column',alignItems:'flex-start'}}><span style={{fontSize:27,fontWeight:950,color:'#fff',direction:'rtl'}}>{brandName}</span><span style={{fontSize:21,fontWeight:900,color:accent,direction:'ltr',letterSpacing:1}}>{brandSite}</span></div>
      </div>
    </div>:null}

    {website&&isWebsite?<AbsoluteFill style={{zIndex:35,background:'radial-gradient(circle at 50% 34%,rgba(244,180,0,.18),rgba(4,15,25,.97) 52%,#02070d 100%)'}}>
      <div style={{position:'absolute',left:52,right:52,top:150,bottom:150,borderRadius:34,overflow:'hidden',background:'#fff',border:'2px solid rgba(244,180,0,.68)',boxShadow:'0 38px 100px rgba(0,0,0,.66)',transform:`translateX(${websiteDrift}%) scale(${websiteScale})`}}>
        <div style={{height:72,display:'flex',alignItems:'center',gap:12,padding:'0 20px',direction:'ltr',background:'#081522',borderBottom:'1px solid rgba(255,255,255,.12)'}}>
          <div style={{display:'flex',gap:7}}><span style={{width:12,height:12,borderRadius:99,background:'#ff5f57'}}/><span style={{width:12,height:12,borderRadius:99,background:'#febc2e'}}/><span style={{width:12,height:12,borderRadius:99,background:'#28c840'}}/></div>
          <div style={{flex:1,height:42,borderRadius:12,background:'rgba(255,255,255,.10)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:21,fontWeight:900,color:'#fff',direction:'ltr'}}>karyabmashin.ir</div>
        </div>
        <div style={{position:'absolute',left:0,right:0,top:72,bottom:0,overflow:'hidden'}}><OffthreadVideo src={website} playbackRate={1.35} muted={true} volume={0} style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:'top center'}}/></div>
      </div>
      <div style={{position:'absolute',right:72,top:116,zIndex:70,padding:'9px 15px',borderRadius:99,background:accent,color:'#081522',fontSize:19,fontWeight:950}}>نمای واقعی سایت</div>
      <div style={{position:'absolute',left:0,right:0,bottom:0,height:500,background:'linear-gradient(180deg,rgba(2,7,13,0),rgba(2,7,13,.92) 42%,#02070d 100%)'}}/>
      {localWebsite>12&&localWebsite<60?<div style={{position:'absolute',right:112,top:320,zIndex:65,width:64,height:64,borderRadius:99,border:`4px solid ${accent}`,boxShadow:`0 0 0 ${10+Math.sin(localWebsite/3)*5}px rgba(244,180,0,.16)`,background:'rgba(255,255,255,.12)'}}/>:null}
    </AbsoluteFill>:null}

    {cue&&!isEnd?<div style={{position:'absolute',left:52,right:52,bottom:isWebsite?226:318,zIndex:100,display:'flex',justifyContent:'center',opacity:cueOpacity,transform:`scale(${cueScale}) translateY(${(1-cueProgress)*12}px)`}}>
      <div style={{maxWidth:970,padding:'20px 32px 24px',borderRadius:24,background:'#020B13',border:`3px solid ${accent}`,boxShadow:'0 28px 84px rgba(0,0,0,.88)',fontSize:frame<70?64:56,lineHeight:1.28,fontWeight:950,color:'#fff',textAlign:'center',textShadow:'0 2px 8px rgba(0,0,0,.72)'}}>{renderAccent(cue.text,cue.accent)}</div>
    </div>:null}

    {website&&frame>=footageEnd-8&&frame<=footageEnd+10?<div style={{position:'absolute',zIndex:130,top:0,bottom:0,left:`${sweep}%`,width:'14%',transform:'skewX(-10deg)',background:'linear-gradient(90deg,rgba(244,180,0,0),rgba(244,180,0,.92),rgba(255,255,255,.95),rgba(244,180,0,0))',filter:'blur(2px)',boxShadow:'0 0 70px rgba(244,180,0,.55)'}}/>:null}
    {frame>=endStart-7&&frame<=endStart+12?<div style={{position:'absolute',zIndex:165,top:0,bottom:0,left:`${endSweep}%`,width:'13%',transform:'skewX(-11deg)',background:'linear-gradient(90deg,rgba(244,180,0,0),rgba(244,180,0,.88),rgba(255,255,255,.92),rgba(244,180,0,0))',filter:'blur(2px)'}}/>:null}

    {isEnd?<AbsoluteFill style={{zIndex:150,alignItems:'center',justifyContent:'center',padding:'80px 64px 122px',background:'radial-gradient(circle at 50% 25%,rgba(244,180,0,.28),rgba(7,24,39,.98) 45%,#02070d 100%)'}}>
      <div style={{width:'100%',display:'flex',flexDirection:'column',alignItems:'center',gap:15,textAlign:'center',opacity:endOpacity,transform:`translateY(${endLift}px)`}}>
        {logo?<Img src={logo} style={{width:170,height:170,objectFit:'contain',filter:'drop-shadow(0 20px 38px rgba(0,0,0,.45))'}}/>:null}
        <div style={{fontSize:67,lineHeight:1.14,fontWeight:980,color:'#fff'}}>{brandName}</div>
        <div style={{fontSize:34,lineHeight:1.35,fontWeight:850,color:'rgba(255,255,255,.84)',maxWidth:900}}>{copy.proof}</div>
        <div style={{marginTop:18,padding:'20px 38px 22px',borderRadius:22,background:accent,color:'#071827',fontSize:44,lineHeight:1.22,fontWeight:980,boxShadow:'0 22px 60px rgba(244,180,0,.24)',transform:`scale(${ctaPulse})`}}>{copy.cta}</div>
        <div style={{marginTop:8,fontSize:35,fontWeight:950,color:accent,direction:'ltr',letterSpacing:1.3}}>{brandSite}</div>
      </div>
    </AbsoluteFill>:null}
  </AbsoluteFill>;
};
