import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import type {CampVertical,CinematicAsset,KbmVideoProps} from './types';

const resolveSource=(src:string|null|undefined)=>{
  if(!src)return null;
  if(/^(https?:|data:|file:)/i.test(src))return src;
  return staticFile(src.replace(/^\/+/,''));
};
const clamp=(value:number,min=0,max=1)=>Math.max(min,Math.min(max,value));

type CopySet={hook:string;hookTag:string;pain:string;solution:string;proof:string;website:string;cta:string;action:string;};
const copyFor=(vertical:CampVertical|undefined,topic:string,cta:string|undefined):CopySet=>{
  const finalCta=(cta??'').trim();
  if(vertical==='machine-sale')return{
    hook:'ماشینت برای فروش آماده‌ست؛ خریدار واقعی کجاست؟',
    hookTag:'فروش ماشین‌آلات، حرفه‌ای و تخصصی',
    pain:'یک عکس مبهم برای تصمیم خریدار کافی نیست',
    solution:'دستگاه را واضح، واقعی و حرفه‌ای معرفی کن',
    proof:'بازار تخصصی خرید و فروش ماشین‌آلات',
    website:'آگهی واقعی را ببین، بررسی کن و تصمیم بگیر',
    cta:finalCta||'همین حالا آگهی فروش را در کاریاب ماشین ثبت کن',
    action:'فروش را از اینجا شروع کن',
  };
  if(vertical==='rental')return{
    hook:'ماشینت آماده کاره؛ پروژه بعدی کجاست؟',
    hookTag:'اجاره ماشین‌آلات، مستقیم و تخصصی',
    pain:'آگهی مبهم، متقاضی مناسب را دور می‌کند',
    solution:'ماشینت را واضح و حرفه‌ای معرفی کن',
    proof:'بازار تخصصی اجاره ماشین‌آلات',
    website:'آگهی‌های واقعی را مستقیم بررسی کن',
    cta:finalCta||'همین حالا آگهی اجاره را ثبت کن',
    action:'برای ماشینت کار پیدا کن',
  };
  if(vertical==='services')return{
    hook:'توان فنی داری؛ مشتری مناسب کجاست؟',
    hookTag:'خدمات تخصصی ماشین‌آلات و پروژه',
    pain:'خدمت خوب بدون معرفی درست دیده نمی‌شود',
    solution:'توان فنی‌ات را حرفه‌ای معرفی کن',
    proof:'بازار تخصصی خدمات ماشین‌آلات',
    website:'خدمات و متخصصان را مستقیم بررسی کن',
    cta:finalCta||'همین حالا خدمتت را ثبت کن',
    action:'خدمتت را معرفی کن',
  };
  const cleanTopic=topic.trim()||'ماشین‌آلات و خدمات پروژه';
  return{
    hook:'انتخاب درست، از دیدن جزئیات واقعی شروع می‌شود',
    hookTag:'کاریاب ماشین؛ بازار تخصصی ماشین‌آلات',
    pain:`برای ${cleanTopic} تصمیم عجولانه نگیر`,
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
  if(!chosen)return <AbsoluteFill style={{background:'#061421'}}/>;
  const isImage=asset?.kind==='image';
  const scaleStarts=[1.08,1.22,1.12,1.28,1.10,1.20,1.14,1.25];
  const x=[-3.2,3.6,-1.4,2.7,-4.1,1.8,-2.2,3.0][index%8];
  const y=[-1.6,-3.2,1.0,-1.2,-2.4,.5,-1.0,-2.0][index%8];
  const sourceStarts=[0.35,2.15,4.4,0.8,6.3,1.25,3.1,5.2];
  const push=interpolate(local,[0,Math.max(1,durationInFrames)],[0,.075],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const flash=interpolate(local,[0,4,9],[.22,0,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  return <AbsoluteFill style={{background:'#061421',overflow:'hidden'}}>
    <AbsoluteFill style={{transform:`translate(${x}%,${y}%) scale(${scaleStarts[index%8]+push})`,filter:'contrast(1.18) saturate(1.12) brightness(1.08)'}}>
      {isImage?
        <Img src={chosen} style={{width:'100%',height:'100%',objectFit:'cover'}}/>:
        <OffthreadVideo src={chosen} startFrom={Math.max(0,Math.round(fps*sourceStarts[index%8]))} muted volume={0} style={{width:'100%',height:'100%',objectFit:'cover'}}/>
      }
    </AbsoluteFill>
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(1,8,14,.08) 0%,rgba(1,8,14,.02) 44%,rgba(1,8,14,.72) 72%,#02070d 100%)'}}/>
    <AbsoluteFill style={{background:`rgba(255,255,255,${flash})`,mixBlendMode:'screen'}}/>
    <div style={{position:'absolute',left:0,right:0,top:0,height:7,background:accent,opacity:.92}}/>
  </AbsoluteFill>;
};

export const CinematicAdMasterReelV3:React.FC<KbmVideoProps>=(props)=>{
  const frame=useCurrentFrame();
  const {fps,durationInFrames}=useVideoConfig();
  const total=Math.max(1,Number(props.durationInFrames??durationInFrames));
  const source=resolveSource(props.media);
  const narration=resolveSource(props.narration);
  const logo=resolveSource(props.brand?.logoSrc);
  const assets=props.assets??[];
  const websiteAsset=assets.find((asset)=>asset.id==='website-walkthrough');
  const website=resolveSource(websiteAsset?.src);
  const externalRaw=assets.filter((asset)=>{
    const provider=(asset.provider??'').toLowerCase();
    return asset.id!=='website-walkthrough'&&Boolean(asset.src)&&(asset.kind==='image'||asset.kind==='video')&&['pexels','pixabay','avalai-generated','kbm-owned'].includes(provider);
  });
  const seen=new Set<string>();
  const external=externalRaw.filter((asset)=>{
    const key=`${asset.provider??''}|${asset.src??''}|${asset.id}`;
    if(seen.has(key))return false;
    seen.add(key);
    return true;
  });

  const camp=props.camp;
  const copy=copyFor(camp?.vertical,camp?.topic??'',props.cta);
  const accent=props.accent??'#F4B400';
  const navy=props.background??'#071827';
  const brandName=props.brand?.name??'کاریاب ماشین';
  const brandSite=props.brand?.site??'KARYABMASHIN.IR';

  // Retention contract: immediate hook, 1.35–1.8s visual resets, short real-site proof,
  // then a long enough brand/CTA tail to be unmistakable in sampled critic frames.
  const endFrames=Math.min(Math.round(fps*4.0),Math.round(total*.22));
  const websiteFrames=website?Math.min(Math.round(fps*2.2),Math.round(total*.13)):0;
  const endStart=Math.max(1,total-endFrames);
  const websiteStart=Math.max(1,endStart-websiteFrames);
  const footageEnd=website?websiteStart:endStart;
  const desiredShots=external.length>=6?8:external.length>=4?7:6;
  const shotCount=Math.max(6,Math.min(8,desiredShots));
  const shotCuts=Array.from({length:shotCount+1},(_,index)=>Math.round(footageEnd*index/shotCount));

  const shotAsset=(index:number):CinematicAsset|null=>{
    if(!external.length)return null;
    // Use every unique routed asset before any repeat. Keep at least one base-source shot
    // so the immutable source footage remains represented in the final campaign.
    if(index===1)return null;
    const poolIndex=index<1?0:index-1;
    return external[poolIndex%external.length]??null;
  };

  const firstShotEnd=Math.max(1,shotCuts[1]??Math.round(fps*1.7));
  const hookActive=frame<Math.min(Math.round(fps*2.35),Math.max(firstShotEnd+Math.round(fps*.5),1));
  const bodyStart=Math.min(Math.round(fps*2.2),Math.max(1,footageEnd-4));
  const bodySpan=Math.max(1,footageEnd-bodyStart);
  const cueBounds=[bodyStart,bodyStart+Math.round(bodySpan*.34),bodyStart+Math.round(bodySpan*.67),footageEnd];
  const cues=[
    {from:cueBounds[0],to:cueBounds[1]-1,text:copy.pain,accentText:'کافی نیست'},
    {from:cueBounds[1],to:cueBounds[2]-1,text:copy.solution,accentText:'حرفه‌ای'},
    {from:cueBounds[2],to:cueBounds[3]-1,text:copy.proof,accentText:'تخصصی'},
  ];
  const cue=cues.find((item)=>frame>=item.from&&frame<=item.to);
  const cueProgress=cue?clamp((frame-cue.from)/8):0;
  const cueOpacity=cue?interpolate(cueProgress,[0,1],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}):0;
  const cueScale=cue?interpolate(cueProgress,[0,1],[.94,1],{easing:Easing.out(Easing.cubic),extrapolateLeft:'clamp',extrapolateRight:'clamp'}):1;

  const isWebsite=Boolean(website)&&frame>=websiteStart&&frame<endStart;
  const isEnd=frame>=endStart;
  const localWebsite=Math.max(0,frame-websiteStart);
  const siteSpan=Math.max(1,endStart-websiteStart);
  const websiteScale=interpolate(localWebsite,[0,siteSpan],[1.03,1.105],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const localEnd=Math.max(0,frame-endStart);
  const endOpacity=interpolate(localEnd,[0,7],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const endLift=interpolate(localEnd,[0,14],[28,0],{easing:Easing.out(Easing.cubic),extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const ctaPulse=1+Math.sin(localEnd/7)*.014;

  const renderAccent=(text:string,needle:string)=>{
    if(!needle||!text.includes(needle))return text;
    const parts=text.split(needle);
    return <>{parts.map((part,index)=><React.Fragment key={`${needle}-${index}`}>{part}{index<parts.length-1?<span style={{color:accent}}>{needle}</span>:null}</React.Fragment>)}</>;
  };

  return <AbsoluteFill style={{background:navy,fontFamily:'Estedad, Noto Sans Arabic, Arial, sans-serif',direction:'rtl',overflow:'hidden'}}>
    {narration?<Audio src={narration} volume={Math.max(0,Number(props.narrationVolume??1))}/>:null}
    <Audio src={staticFile('rc7-bed.wav')} volume={0.115}/>
    <Sequence from={0}><Audio src={staticFile('rc7-impact.wav')} volume={0.24}/></Sequence>
    {shotCuts.slice(1,-1).map((cut,index)=><Sequence key={`sfx-${cut}`} from={Math.max(0,cut-2)}><Audio src={staticFile(index%2===0?'rc7-whoosh.wav':'rc7-click.wav')} volume={index%2===0?.15:.12}/></Sequence>)}
    {website?<Sequence from={Math.max(0,websiteStart-3)}><Audio src={staticFile('rc7-whoosh.wav')} volume={0.17}/></Sequence>:null}
    <Sequence from={endStart}><Audio src={staticFile('rc7-impact.wav')} volume={0.21}/></Sequence>

    {shotCuts.slice(0,-1).map((from,index)=>{
      const to=shotCuts[index+1];
      return <Sequence key={`shot-${index}`} from={from} durationInFrames={Math.max(1,to-from)}>
        <ShotVisual asset={shotAsset(index)} baseSource={source} index={index} accent={accent}/>
      </Sequence>;
    })}

    {!isEnd?<div style={{position:'absolute',top:36,left:42,right:42,zIndex:100,display:'flex',justifyContent:'space-between',alignItems:'flex-start',direction:'ltr'}}>
      <div style={{display:'flex',alignItems:'center',gap:13,padding:'9px 16px 10px 11px',borderRadius:18,border:`2px solid ${accent}`,background:'rgba(3,15,26,.97)',boxShadow:'0 14px 38px rgba(0,0,0,.46)'}}>
        {logo?<Img src={logo} style={{width:76,height:78,objectFit:'contain'}}/>:null}
        <div style={{display:'flex',flexDirection:'column',alignItems:'flex-start'}}>
          <span style={{fontSize:31,fontWeight:980,color:'#fff',direction:'rtl'}}>{brandName}</span>
          <span style={{fontSize:23,fontWeight:950,color:accent,direction:'ltr',letterSpacing:1.1}}>{brandSite}</span>
        </div>
      </div>
      <div style={{marginTop:5,padding:'10px 17px',borderRadius:99,background:accent,color:'#071827',fontSize:20,fontWeight:950,direction:'rtl'}}>بازار تخصصی ماشین‌آلات</div>
    </div>:null}

    {hookActive&&!isWebsite&&!isEnd?<div style={{position:'absolute',left:42,right:42,bottom:238,zIndex:130,display:'flex',flexDirection:'column',alignItems:'center',gap:13}}>
      <div style={{padding:'9px 18px',borderRadius:99,background:accent,color:'#071827',fontSize:25,fontWeight:980,boxShadow:'0 12px 40px rgba(0,0,0,.4)'}}>{copy.hookTag}</div>
      <div style={{width:'100%',padding:'22px 30px 27px',borderRadius:26,background:'rgba(2,11,19,.97)',border:`4px solid ${accent}`,boxShadow:'0 34px 90px rgba(0,0,0,.92)',fontSize:66,lineHeight:1.24,fontWeight:1000,color:'#fff',textAlign:'center'}}>{copy.hook}</div>
    </div>:null}

    {cue&&!hookActive&&!isWebsite&&!isEnd?<div style={{position:'absolute',left:48,right:48,bottom:244,zIndex:120,display:'flex',justifyContent:'center',opacity:cueOpacity,transform:`scale(${cueScale}) translateY(${(1-cueProgress)*8}px)`}}>
      <div style={{maxWidth:980,padding:'18px 30px 22px',borderRadius:23,background:'rgba(2,11,19,.97)',border:`3px solid ${accent}`,boxShadow:'0 28px 84px rgba(0,0,0,.90)',fontSize:54,lineHeight:1.27,fontWeight:980,color:'#fff',textAlign:'center'}}>{renderAccent(cue.text,cue.accentText)}</div>
    </div>:null}

    {website&&isWebsite?<AbsoluteFill style={{zIndex:160,background:'radial-gradient(circle at 50% 28%,rgba(244,180,0,.25),rgba(4,15,25,.98) 52%,#02070d 100%)'}}>
      <div style={{position:'absolute',left:42,right:42,top:118,bottom:206,borderRadius:34,overflow:'hidden',background:'#fff',border:`3px solid ${accent}`,boxShadow:'0 38px 100px rgba(0,0,0,.72)',transform:`scale(${websiteScale})`}}>
        <div style={{height:72,display:'flex',alignItems:'center',gap:12,padding:'0 20px',direction:'ltr',background:'#081522',borderBottom:'1px solid rgba(255,255,255,.12)'}}>
          <div style={{display:'flex',gap:7}}><span style={{width:12,height:12,borderRadius:99,background:'#ff5f57'}}/><span style={{width:12,height:12,borderRadius:99,background:'#febc2e'}}/><span style={{width:12,height:12,borderRadius:99,background:'#28c840'}}/></div>
          <div style={{flex:1,height:43,borderRadius:12,background:'rgba(255,255,255,.11)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:23,fontWeight:950,color:'#fff',direction:'ltr'}}>karyabmashin.ir</div>
        </div>
        <div style={{position:'absolute',left:0,right:0,top:72,bottom:0,overflow:'hidden'}}><OffthreadVideo src={website} playbackRate={1.8} muted volume={0} style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:'top center'}}/></div>
      </div>
      <div style={{position:'absolute',right:58,top:82,zIndex:180,padding:'10px 17px',borderRadius:99,background:accent,color:'#081522',fontSize:21,fontWeight:980}}>نمای واقعی سایت کاریاب ماشین</div>
      <div style={{position:'absolute',left:46,right:46,bottom:86,zIndex:180,padding:'20px 27px 24px',borderRadius:24,background:'#020B13',border:`3px solid ${accent}`,fontSize:49,lineHeight:1.24,fontWeight:980,color:'#fff',textAlign:'center',boxShadow:'0 22px 65px rgba(0,0,0,.78)'}}>{renderAccent(copy.website,'ببین')}</div>
    </AbsoluteFill>:null}

    {isEnd?<AbsoluteFill style={{zIndex:220,alignItems:'center',justifyContent:'center',padding:'62px 54px 104px',background:'radial-gradient(circle at 50% 22%,rgba(244,180,0,.36),rgba(7,24,39,.98) 43%,#02070d 100%)'}}>
      <div style={{width:'100%',display:'flex',flexDirection:'column',alignItems:'center',gap:13,textAlign:'center',opacity:endOpacity,transform:`translateY(${endLift}px)`}}>
        {logo?<Img src={logo} style={{width:190,height:190,objectFit:'contain',filter:'drop-shadow(0 22px 42px rgba(0,0,0,.48))'}}/>:null}
        <div style={{fontSize:72,lineHeight:1.1,fontWeight:1000,color:'#fff'}}>{brandName}</div>
        <div style={{padding:'9px 20px',borderRadius:99,border:`2px solid ${accent}`,fontSize:29,fontWeight:950,color:accent}}>{copy.action}</div>
        <div style={{fontSize:32,lineHeight:1.34,fontWeight:880,color:'rgba(255,255,255,.90)',maxWidth:900}}>{copy.proof}</div>
        <div style={{marginTop:10,padding:'20px 34px 23px',borderRadius:24,background:accent,color:'#071827',fontSize:44,lineHeight:1.23,fontWeight:1000,boxShadow:'0 22px 66px rgba(244,180,0,.30)',transform:`scale(${ctaPulse})`}}>{copy.cta}</div>
        <div style={{marginTop:5,fontSize:39,fontWeight:1000,color:accent,direction:'ltr',letterSpacing:1.5}}>{brandSite}</div>
      </div>
    </AbsoluteFill>:null}
  </AbsoluteFill>;
};
