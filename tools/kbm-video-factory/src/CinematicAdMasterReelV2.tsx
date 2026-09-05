import React from 'react';
import {AbsoluteFill,Audio,Easing,Img,OffthreadVideo,Sequence,interpolate,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';
import type {CampVertical,CinematicAsset,KbmVideoProps} from './types';

const resolveSource=(src:string|null|undefined)=>{if(!src)return null;if(/^(https?:|data:|file:)/i.test(src))return src;return staticFile(src.replace(/^\/+/,''));};
const clamp=(value:number,min=0,max=1)=>Math.max(min,Math.min(max,value));
const score=(value:unknown)=>{const n=Number(value??0);return Number.isFinite(n)?n:0;};

type CopySet={hook:string;pain:string;solution:string;proof:string;website:string;cta:string;action:string;};
const copyFor=(vertical:CampVertical|undefined,topic:string,cta:string|undefined):CopySet=>{
  const finalCta=(cta??'').trim();
  if(vertical==='machine-sale')return{
    hook:'ماشینت خوابیده؟ خریدار واقعی کجاست؟',
    pain:'فقط یک عکس برای فروش کافی نیست',
    solution:'دستگاه را واضح و حرفه‌ای معرفی کن',
    proof:'بازار تخصصی خرید و فروش ماشین‌آلات',
    website:'آگهی را ببین، بررسی کن و تصمیم بگیر',
    cta:finalCta||'همین حالا آگهی فروش را ثبت کن',
    action:'فروش را از اینجا شروع کن',
  };
  if(vertical==='rental')return{
    hook:'ماشینت آماده کاره؛ پروژه بعدی کجاست؟',
    pain:'آگهی مبهم، متقاضی مناسب را دور می‌کند',
    solution:'ماشینت را واضح و حرفه‌ای معرفی کن',
    proof:'بازار تخصصی اجاره ماشین‌آلات',
    website:'آگهی‌های واقعی را مستقیم بررسی کن',
    cta:finalCta||'همین حالا آگهی اجاره را ثبت کن',
    action:'برای ماشینت کار پیدا کن',
  };
  if(vertical==='services')return{
    hook:'توان فنی داری؛ مشتری مناسب کجاست؟',
    pain:'خدمت خوب بدون معرفی درست دیده نمی‌شود',
    solution:'توان فنی‌ات را حرفه‌ای معرفی کن',
    proof:'بازار تخصصی خدمات ماشین‌آلات',
    website:'خدمات و متخصصان را مستقیم بررسی کن',
    cta:finalCta||'همین حالا خدمتت را ثبت کن',
    action:'خدمتت را معرفی کن',
  };
  const cleanTopic=topic.trim()||'ماشین‌آلات و خدمات پروژه';
  return{
    hook:'انتخاب درست، از دیدن جزئیات شروع می‌شود',
    pain:`برای ${cleanTopic} تصمیم عجولانه نکن`,
    solution:'اطلاعات را واضح ببین و مقایسه کن',
    proof:'کاریاب ماشین؛ مسیر تخصصی ماشین‌آلات و پروژه',
    website:'جزئیات واقعی را در سایت ببین',
    cta:finalCta||'همین حالا وارد کاریاب ماشین شو',
    action:'همین حالا بررسی کن',
  };
};

type ShotVisualProps={asset?:CinematicAsset|null;baseSource:string|null;index:number;accent:string;};
const ShotVisual:React.FC<ShotVisualProps>=({asset,baseSource,index,accent})=>{
  const local=useCurrentFrame();
  const {fps,durationInFrames}=useVideoConfig();
  const chosen=resolveSource(asset?.src)||baseSource;
  if(!chosen)return <AbsoluteFill style={{background:'#071827'}}/>;
  const isImage=asset?.kind==='image';
  const baseScale=[1.16,1.27,1.11,1.31,1.18,1.25,1.13][index%7];
  const push=interpolate(local,[0,Math.max(1,durationInFrames)],[0,.055],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const x=[-2.4,2.8,-3.5,3.1,-1.5,2.0,-2.8][index%7];
  const y=[-1.0,-2.0,1.2,-1.5,-2.2,.8,-1.2][index%7];
  const startSeconds=[1.8,3.4,0.3,5.2,0.8,7.0,2.4][index%7];
  return <AbsoluteFill style={{background:'#061421',overflow:'hidden'}}>
    <AbsoluteFill style={{transform:`translate(${x}%,${y}%) scale(${baseScale+push})`,filter:'contrast(1.14) saturate(1.08) brightness(1.10)'}}>
      {isImage?<Img src={chosen} style={{width:'100%',height:'100%',objectFit:'cover'}}/>:<OffthreadVideo src={chosen} startFrom={Math.max(0,Math.round(fps*startSeconds))} muted={true} volume={0} style={{width:'100%',height:'100%',objectFit:'cover'}}/>}
    </AbsoluteFill>
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(2,9,16,.18) 0%,rgba(2,9,16,.02) 46%,rgba(2,7,13,.78) 70%,#02070d 88%,#02070d 100%)'}}/>
    <div style={{position:'absolute',left:0,right:0,bottom:0,height:610,background:'linear-gradient(180deg,rgba(2,7,13,.15),rgba(2,7,13,.96) 24%,#02070d 48%,#02070d 100%)'}}/>
    <div style={{position:'absolute',left:0,right:0,top:0,height:8,background:accent,opacity:.78}}/>
  </AbsoluteFill>;
};

export const CinematicAdMasterReelV2:React.FC<KbmVideoProps>=(props)=>{
  const frame=useCurrentFrame();
  const {fps,durationInFrames}=useVideoConfig();
  const total=Math.max(1,Number(props.durationInFrames??durationInFrames));
  const source=resolveSource(props.media);
  const narration=resolveSource(props.narration);
  const logo=resolveSource(props.brand?.logoSrc);
  const assets=props.assets??[];
  const websiteAsset=assets.find((asset)=>asset.id==='website-walkthrough');
  const website=resolveSource(websiteAsset?.src);
  const external=assets.filter((asset)=>{
    const provider=(asset.provider??'').toLowerCase();
    return asset.id!=='website-walkthrough'&&Boolean(asset.src)&&(asset.kind==='image'||asset.kind==='video')&&['pexels','pixabay','avalai-generated'].includes(provider);
  });
  const heroAsset=external.find((asset)=>asset.kind==='image')??external[0]??null;
  const motionAsset=external.find((asset)=>asset.kind==='video')??external.find((asset)=>asset!==heroAsset)??null;
  const camp=props.camp;
  const copy=copyFor(camp?.vertical,camp?.topic??'',props.cta);
  const accent=props.accent??'#F4B400';
  const navy=props.background??'#071827';
  const brandName=props.brand?.name??'کاریاب ماشین';
  const brandSite=props.brand?.site??'KARYABMASHIN.IR';

  const critic=(props.editorial?.avalaiCritic??{}) as Record<string,unknown>;
  const repairMode=Number(props.editorial?.repairPass??0)>0;
  const needsVariety=repairMode&&(score(critic.pacing)<8||score(critic.shotVariety)<8||score(critic.brollRelevance)<8.3);
  const needsCta=repairMode&&score(critic.ctaStrength)<8.3;
  const shotCount=needsVariety?7:6;
  const endFrames=Math.min(Math.round(fps*(needsCta?3.8:3.35)),Math.round(total*.24));
  const websiteFrames=website?Math.min(Math.round(fps*(needsVariety?2.35:3.0)),Math.round(total*.18)):0;
  const endStart=Math.max(1,total-endFrames);
  const websiteStart=Math.max(1,endStart-websiteFrames);
  const footageEnd=website?websiteStart:endStart;
  const shotCuts=Array.from({length:shotCount+1},(_,index)=>Math.round(footageEnd*index/shotCount));

  const shotAsset=(index:number):CinematicAsset|null=>{
    if(index===0&&heroAsset)return heroAsset;
    if(index===2&&motionAsset)return motionAsset;
    if(index===4&&heroAsset)return heroAsset;
    if(needsVariety&&index===5&&motionAsset)return motionAsset;
    return null;
  };

  const cueBounds=[0,Math.round(footageEnd*.24),Math.round(footageEnd*.49),Math.round(footageEnd*.74),footageEnd];
  const cues=[
    {from:cueBounds[0],to:cueBounds[1]-1,text:copy.hook,accent:'واقعی'},
    {from:cueBounds[1],to:cueBounds[2]-1,text:copy.pain,accent:'کافی نیست'},
    {from:cueBounds[2],to:cueBounds[3]-1,text:copy.solution,accent:'حرفه‌ای'},
    {from:cueBounds[3],to:cueBounds[4]-1,text:copy.proof,accent:'تخصصی'},
  ];
  const cue=cues.find((item)=>frame>=item.from&&frame<=item.to);
  const cueProgress=cue?clamp((frame-cue.from)/Math.max(1,Math.min(10,cue.to-cue.from))):0;
  const cueOpacity=cue?interpolate(cueProgress,[0,1],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}):0;
  const cueScale=cue?interpolate(cueProgress,[0,1],[.92,1],{easing:Easing.out(Easing.cubic),extrapolateLeft:'clamp',extrapolateRight:'clamp'}):1;
  const isWebsite=Boolean(website)&&frame>=websiteStart&&frame<endStart;
  const isEnd=frame>=endStart;
  const localWebsite=Math.max(0,frame-websiteStart);
  const siteSpan=Math.max(1,endStart-websiteStart);
  const websiteScale=interpolate(localWebsite,[0,siteSpan],[1.025,1.09],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const websiteDrift=interpolate(localWebsite,[0,siteSpan],[-1.0,1.3],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const localEnd=Math.max(0,frame-endStart);
  const endOpacity=interpolate(localEnd,[0,9],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const endLift=interpolate(localEnd,[0,16],[34,0],{easing:Easing.out(Easing.cubic),extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const ctaPulse=1+Math.sin(localEnd/8)*.012;

  const renderAccent=(text:string,needle:string)=>{
    if(!needle||!text.includes(needle))return text;
    const parts=text.split(needle);
    return <>{parts.map((part,index)=><React.Fragment key={`${needle}-${index}`}>{part}{index<parts.length-1?<span style={{color:accent}}>{needle}</span>:null}</React.Fragment>)}</>;
  };

  return <AbsoluteFill style={{background:navy,fontFamily:'Estedad, Noto Sans Arabic, Arial, sans-serif',direction:'rtl',overflow:'hidden'}}>
    {narration?<Audio src={narration} volume={Math.max(0,Number(props.narrationVolume??1))}/>:null}
    <Audio src={staticFile('rc7-bed.wav')} volume={0.12}/>
    <Sequence from={0}><Audio src={staticFile('rc7-impact.wav')} volume={0.20}/></Sequence>
    {shotCuts.slice(1,-1).map((cut,index)=><Sequence key={`sfx-${cut}`} from={Math.max(0,cut-2)}><Audio src={staticFile(index%2===0?'rc7-whoosh.wav':'rc7-click.wav')} volume={index%2===0?.13:.11}/></Sequence>)}
    {website?<Sequence from={Math.max(0,websiteStart-3)}><Audio src={staticFile('rc7-whoosh.wav')} volume={0.16}/></Sequence>:null}
    <Sequence from={endStart}><Audio src={staticFile('rc7-impact.wav')} volume={0.18}/></Sequence>

    {shotCuts.slice(0,-1).map((from,index)=>{
      const to=shotCuts[index+1];
      return <Sequence key={`shot-${index}`} from={from} durationInFrames={Math.max(1,to-from)}>
        <ShotVisual asset={shotAsset(index)} baseSource={source} index={index} accent={accent}/>
      </Sequence>;
    })}

    {!isEnd?<div style={{position:'absolute',top:42,left:50,right:50,zIndex:90,display:'flex',justifyContent:'flex-start',direction:'ltr'}}>
      <div style={{display:'flex',alignItems:'center',gap:12,padding:'8px 14px 9px 10px',borderRadius:17,border:`1.8px solid ${accent}`,background:'rgba(4,17,29,.96)',boxShadow:'0 14px 34px rgba(0,0,0,.40)'}}>
        {logo?<Img src={logo} style={{width:62,height:65,objectFit:'contain'}}/>:null}
        <div style={{display:'flex',flexDirection:'column',alignItems:'flex-start'}}><span style={{fontSize:27,fontWeight:950,color:'#fff',direction:'rtl'}}>{brandName}</span><span style={{fontSize:21,fontWeight:900,color:accent,direction:'ltr',letterSpacing:1}}>{brandSite}</span></div>
      </div>
    </div>:null}

    {website&&isWebsite?<AbsoluteFill style={{zIndex:50,background:'radial-gradient(circle at 50% 32%,rgba(244,180,0,.20),rgba(4,15,25,.98) 54%,#02070d 100%)'}}>
      <div style={{position:'absolute',left:48,right:48,top:142,bottom:190,borderRadius:32,overflow:'hidden',background:'#fff',border:'2px solid rgba(244,180,0,.78)',boxShadow:'0 38px 100px rgba(0,0,0,.68)',transform:`translateX(${websiteDrift}%) scale(${websiteScale})`}}>
        <div style={{height:70,display:'flex',alignItems:'center',gap:12,padding:'0 20px',direction:'ltr',background:'#081522',borderBottom:'1px solid rgba(255,255,255,.12)'}}>
          <div style={{display:'flex',gap:7}}><span style={{width:12,height:12,borderRadius:99,background:'#ff5f57'}}/><span style={{width:12,height:12,borderRadius:99,background:'#febc2e'}}/><span style={{width:12,height:12,borderRadius:99,background:'#28c840'}}/></div>
          <div style={{flex:1,height:42,borderRadius:12,background:'rgba(255,255,255,.10)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:21,fontWeight:900,color:'#fff',direction:'ltr'}}>karyabmashin.ir</div>
        </div>
        <div style={{position:'absolute',left:0,right:0,top:70,bottom:0,overflow:'hidden'}}><OffthreadVideo src={website} playbackRate={1.65} muted={true} volume={0} style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:'top center'}}/></div>
      </div>
      <div style={{position:'absolute',right:70,top:110,zIndex:70,padding:'9px 15px',borderRadius:99,background:accent,color:'#081522',fontSize:19,fontWeight:950}}>نمای واقعی سایت</div>
      <div style={{position:'absolute',left:52,right:52,bottom:92,zIndex:80,padding:'18px 26px 22px',borderRadius:22,background:'#020B13',border:`2px solid ${accent}`,fontSize:48,lineHeight:1.25,fontWeight:950,color:'#fff',textAlign:'center',boxShadow:'0 22px 65px rgba(0,0,0,.75)'}}>{renderAccent(copy.website,'ببین')}</div>
    </AbsoluteFill>:null}

    {cue&&!isWebsite&&!isEnd?<div style={{position:'absolute',left:48,right:48,bottom:245,zIndex:100,display:'flex',justifyContent:'center',opacity:cueOpacity,transform:`scale(${cueScale}) translateY(${(1-cueProgress)*10}px)`}}>
      <div style={{maxWidth:980,padding:'18px 30px 22px',borderRadius:23,background:'#020B13',border:`3px solid ${accent}`,boxShadow:'0 28px 84px rgba(0,0,0,.90)',fontSize:frame<90?62:54,lineHeight:1.27,fontWeight:950,color:'#fff',textAlign:'center',textShadow:'0 2px 8px rgba(0,0,0,.72)'}}>{renderAccent(cue.text,cue.accent)}</div>
    </div>:null}

    {isEnd?<AbsoluteFill style={{zIndex:150,alignItems:'center',justifyContent:'center',padding:'72px 60px 110px',background:'radial-gradient(circle at 50% 24%,rgba(244,180,0,.30),rgba(7,24,39,.98) 44%,#02070d 100%)'}}>
      <div style={{width:'100%',display:'flex',flexDirection:'column',alignItems:'center',gap:14,textAlign:'center',opacity:endOpacity,transform:`translateY(${endLift}px)`}}>
        {logo?<Img src={logo} style={{width:158,height:158,objectFit:'contain',filter:'drop-shadow(0 20px 38px rgba(0,0,0,.45))'}}/>:null}
        <div style={{fontSize:64,lineHeight:1.12,fontWeight:980,color:'#fff'}}>{brandName}</div>
        <div style={{padding:'8px 18px',borderRadius:99,border:`1px solid ${accent}`,fontSize:27,fontWeight:900,color:accent}}>{copy.action}</div>
        <div style={{fontSize:31,lineHeight:1.34,fontWeight:840,color:'rgba(255,255,255,.86)',maxWidth:900}}>{copy.proof}</div>
        <div style={{marginTop:12,padding:'18px 34px 21px',borderRadius:22,background:accent,color:'#071827',fontSize:42,lineHeight:1.24,fontWeight:980,boxShadow:'0 22px 60px rgba(244,180,0,.26)',transform:`scale(${ctaPulse})`}}>{copy.cta}</div>
        <div style={{marginTop:6,fontSize:35,fontWeight:950,color:accent,direction:'ltr',letterSpacing:1.3}}>{brandSite}</div>
      </div>
    </AbsoluteFill>:null}
  </AbsoluteFill>;
};
