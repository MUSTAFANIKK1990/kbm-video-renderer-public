import React from 'react';
import {AbsoluteFill,Audio,Img,OffthreadVideo,Sequence,interpolate,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';
import type {CinematicAsset,KbmVideoProps} from './types';

const src=(value:string|null|undefined)=>value?(/^(https?:|data:|file:)/i.test(value)?value:staticFile(value.replace(/^\/+/,''))):null;
const clamp=(v:number)=>Math.max(0,Math.min(1,v));

type RepairFlags={hook?:boolean;pacing?:boolean;broll?:boolean;shotVariety?:boolean;caption?:boolean;cta?:boolean;brand?:boolean;stagnation?:boolean;};
type ReferenceEditingProfile={profileId?:string;hookMaxSeconds?:number;visualResetTargetSeconds?:number;endCardMinSeconds?:number;proofBadges?:string[];};

const Visual:React.FC<{asset:CinematicAsset|null;base:string|null;index:number;accent:string;fast:boolean}>=({asset,base,index,accent,fast})=>{
  const frame=useCurrentFrame();
  const {fps,durationInFrames}=useVideoConfig();
  const chosen=src(asset?.src)||base;
  if(!chosen)return <AbsoluteFill style={{background:'#061421'}}/>;
  const starts=[.2,1.5,3.2,.8,4.7,2.4,5.6,1.1];
  const scales=[1.05,1.15,1.09,1.19,1.07,1.14,1.10,1.17];
  const progress=clamp(frame/Math.max(1,durationInFrames-1));
  const move=interpolate(frame,[0,Math.max(1,durationInFrames)],[0,fast?.12:.07],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const direction=index%2===0?1:-1;
  const panX=direction*interpolate(progress,[0,1],[-28,30]);
  const panY=(index%3-1)*interpolate(progress,[0,1],[18,-22]);
  const rotate=direction*interpolate(progress,[0,1],[-.28,.24]);
  const entry=interpolate(frame,[0,Math.max(5,Math.round(fps*.20))],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  return <AbsoluteFill style={{background:'#061421',overflow:'hidden'}}>
    <AbsoluteFill style={{transform:`translate3d(${panX}px,${panY}px,0) scale(${scales[index%8]+move}) rotate(${rotate}deg)`,filter:'contrast(1.16) saturate(1.10) brightness(1.08)'}}>
      {asset?.kind==='image'?<Img src={chosen} style={{width:'100%',height:'100%',objectFit:'cover'}}/>:<OffthreadVideo src={chosen} startFrom={Math.round(fps*starts[index%8])} muted volume={0} style={{width:'100%',height:'100%',objectFit:'cover'}}/>}
    </AbsoluteFill>
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(2,9,16,.04),rgba(2,9,16,.08) 48%,rgba(2,7,13,.76) 76%,#02070d)'}}/>
    <AbsoluteFill style={{background:`linear-gradient(${direction>0?'90deg':'270deg'},${accent},rgba(244,180,0,0))`,opacity:(1-entry)*.34,transform:`translateX(${direction*(entry*110-110)}%)`}}/>
    <div style={{position:'absolute',top:0,left:0,right:0,height:7,background:accent}}/>
  </AbsoluteFill>;
};

export const CinematicAdMasterReelV4:React.FC<KbmVideoProps>=(props)=>{
  const frame=useCurrentFrame();
  const {fps,durationInFrames}=useVideoConfig();
  const total=Math.max(1,Number(props.durationInFrames??durationInFrames));
  const base=src(props.media);
  const narration=src(props.narration);
  const logo=src(props.brand?.logoSrc);
  const accent=props.accent??'#F4B400';
  const navy=props.background??'#071827';
  const brand=props.brand?.name??'کاریاب ماشین';
  const site=props.brand?.site??'KARYABMASHIN.IR';
  const assets=props.assets??[];
  const webAsset=assets.find((a)=>a.id==='website-walkthrough');
  const website=src(webAsset?.src);
  const raw=assets.filter((a)=>a.id!=='website-walkthrough'&&Boolean(a.src)&&(a.kind==='image'||a.kind==='video')&&['pexels','pixabay','cupai-generated','kbm-owned'].includes((a.provider??'').toLowerCase()));
  const seen=new Set<string>();
  const external=raw.filter((a)=>{const k=`${a.provider??''}|${a.src??''}`;if(seen.has(k))return false;seen.add(k);return true;});
  const editorial=(props.editorial??{}) as typeof props.editorial&{repairFlags?:RepairFlags;preserveMixedAudio?:boolean;referenceEditingProfile?:ReferenceEditingProfile};
  const repair=Math.max(0,Number(editorial.repairPass??0));
  const preserveMixedAudio=Boolean(editorial.preserveMixedAudio);
  const flags=editorial.repairFlags??{};
  const fast=repair>0||Boolean(flags.pacing||flags.shotVariety||flags.stagnation);
  const reference=editorial.referenceEditingProfile??{};
  const configuredReset=Number(reference.visualResetTargetSeconds??1.55);
  const visualResetSeconds=Number.isFinite(configuredReset)?Math.max(1.25,Math.min(2,configuredReset)):1.55;
  const configuredHook=Number(reference.hookMaxSeconds??1.5);
  const hookMaxSeconds=Number.isFinite(configuredHook)?Math.max(.8,Math.min(2,configuredHook)):1.5;
  const proofBadges=(Array.isArray(reference.proofBadges)?reference.proofBadges:[]).filter((item)=>Boolean(item&&item.trim())) || [];
  if(!proofBadges.length)proofBadges.push('مشاهده دقیق','مقایسه واقعی','اقدام سریع');

  const machineSale=props.camp?.vertical==='machine-sale';
  const hook=machineSale?(repair?'ماشینت هنوز فروش نرفته؟':'ماشینت برای فروش آماده‌ست؟'):'جزئیات واقعی را دیدی؟';
  const hookTag=machineSale?(repair?'بازدید هست، تماس نیست؟':'خریدار واقعی کجاست؟'):'قبل از تصمیم، بررسی کن';
  const messages=machineSale?['عکس واضح، اعتماد خریدار را می‌سازد','جزئیات واقعی دستگاه را نشان بده','در بازار تخصصی، مستقیم دیده شو']:['اطلاعات را واضح ببین','گزینه‌ها را مقایسه کن','کاریاب ماشین؛ بازار تخصصی'];
  const requestedCta=(props.cta??'').trim();
  const ctaAction=machineSale?(repair?'وارد سایت شو؛ آگهی ماشینت را همین حالا ثبت کن':'همین حالا آگهی فروش ماشینت را ثبت کن'):(requestedCta||'همین حالا سایت کاریاب ماشین را بررسی کن');

  // Hotfix06: keep the final conversion moment visible long enough for two critic samples,
  // but animate the lockup so the end card does not become a static >2.5s stagnation risk.
  const endFrames=Math.round(fps*(machineSale?(repair?4.2:3.9):(flags.cta||flags.brand?3.7:3.35)));
  const endStart=Math.max(1,total-endFrames);
  const websiteStart=website?Math.round(fps*(repair>=2?9.6:10.8)):0;
  const websiteEnd=website?Math.min(endStart-Math.round(.45*fps),websiteStart+Math.round((repair>=2?3.35:2.5)*fps)):0;

  // Repair passes use every unique licensed asset without falling back to an already-captioned source frame.
  const plan:(CinematicAsset|null)[]=external.slice(0,repair>0?8:7);
  if(repair===0)plan.splice(Math.min(2,plan.length),0,null);
  const visuals=plan.slice(0,8);
  if(!visuals.length)visuals.push(null);
  const cuts=Array.from({length:visuals.length+1},(_,i)=>Math.round(endStart*i/visuals.length));

  const hookEnd=Math.round(fps*hookMaxSeconds);
  const bodyStart=hookEnd;
  const span=Math.max(1,endStart-bodyStart);
  const bounds=[bodyStart,bodyStart+Math.round(span*.32),bodyStart+Math.round(span*.64),endStart];
  const cueIndex=frame<bounds[1]?0:frame<bounds[2]?1:2;
  const cueActive=frame>=bodyStart&&frame<endStart&&!((website&&frame>=websiteStart&&frame<websiteEnd));
  const cueIn=clamp((frame-bounds[Math.min(2,cueIndex)])/7);
  const cueBottom=[430,340,390][cueIndex]??370;
  const cueInset=[54,112,72][cueIndex]??54;
  const cueFill=cueIndex===1?accent:'rgba(2,11,19,.97)';
  const cueColor=cueIndex===1?'#071827':'#fff';
  const cueShift=(cueIndex===0?-1:cueIndex===2?1:0)*(1-cueIn)*46;
  const proofBeatFrames=Math.max(1,Math.round(fps*visualResetSeconds));
  const proofIndex=Math.max(0,Math.floor((frame-hookEnd)/proofBeatFrames));
  const proofBadge=proofBadges[proofIndex%proofBadges.length];
  const proofLocal=Math.max(0,(frame-hookEnd)%proofBeatFrames);
  const proofIn=interpolate(proofLocal,[0,6,Math.max(8,Math.round(fps*.46))],[0,1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const proofShift=(1-proofIn)*(proofIndex%2===0?36:-36);
  const endLocal=Math.max(0,frame-endStart);
  const endOpacity=interpolate(endLocal,[0,6],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const logoScale=interpolate(endLocal,[0,12],[.82,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const brandOpacity=interpolate(endLocal,[4,14],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const ctaOpacity=interpolate(endLocal,[13,25],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const siteOpacity=interpolate(endLocal,[22,34],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const haloShift=interpolate(endLocal,[0,Math.max(1,endFrames)],[18,34],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});

  return <AbsoluteFill style={{background:navy,fontFamily:'Estedad, Noto Sans Arabic, Arial, sans-serif',direction:'rtl',overflow:'hidden'}}>
    {narration?<Audio src={narration} volume={Math.max(0,Number(props.narrationVolume??1))}/>:null}
    {!preserveMixedAudio?<><Audio src={staticFile('rc7-bed.wav')} volume={.115}/><Sequence from={0}><Audio src={staticFile('rc7-impact.wav')} volume={.24}/></Sequence>{cuts.slice(1,-1).map((cut,i)=><Sequence key={`sfx-${cut}`} from={Math.max(0,cut-2)}><Audio src={staticFile(i%2?'rc7-click.wav':'rc7-whoosh.wav')} volume={.14}/></Sequence>)}<Sequence from={endStart}><Audio src={staticFile('rc7-impact.wav')} volume={.22}/></Sequence></>:null}

    {visuals.map((asset,i)=><Sequence key={`shot-${i}`} from={cuts[i]} durationInFrames={Math.max(1,cuts[i+1]-cuts[i])}><Visual asset={asset} base={base} index={i} accent={accent} fast={fast}/></Sequence>)}

    {frame<endStart?<div style={{position:'absolute',top:38,left:42,right:42,zIndex:100,display:'flex',justifyContent:'space-between',direction:'ltr'}}>
      <div style={{display:'flex',alignItems:'center',gap:9,padding:'7px 12px',borderRadius:17,border:`2px solid ${accent}`,background:'rgba(3,15,26,.94)'}}>{logo?<Img src={logo} style={{width:54,height:56,objectFit:'contain'}}/>:null}<div style={{fontSize:26,fontWeight:980,color:'#fff',direction:'rtl'}}>{brand}</div></div>
      <div style={{marginTop:5,padding:'8px 14px',borderRadius:99,background:'rgba(244,180,0,.94)',color:'#071827',fontSize:18,fontWeight:950,direction:'rtl'}}>بازار تخصصی ماشین‌آلات</div>
    </div>:null}

    {cueActive&&frame>=hookEnd?<div style={{position:'absolute',top:154,right:44,zIndex:135,display:'flex',alignItems:'center',gap:10,opacity:proofIn,transform:'translateX('+proofShift+'px) scale('+(0.9+0.1*proofIn)+')',direction:'rtl'}}><div style={{width:54,height:54,borderRadius:99,background:accent,color:'#071827',display:'flex',alignItems:'center',justifyContent:'center',fontSize:27,fontWeight:1000}}>{(proofIndex%3)+1}</div><div style={{padding:'10px 17px',borderRadius:18,background:'rgba(2,11,19,.95)',border:'2px solid '+accent,fontSize:25,fontWeight:950,color:'#fff'}}>{proofBadge}</div></div>:null}

    {frame<hookEnd?<div style={{position:'absolute',left:42,right:42,bottom:335,zIndex:130,textAlign:'center'}}><div style={{display:'inline-block',padding:'8px 18px',borderRadius:99,background:accent,color:'#071827',fontSize:26,fontWeight:1000}}>{hookTag}</div><div style={{marginTop:12,padding:'22px 28px',borderRadius:26,background:'rgba(2,11,19,.97)',border:`4px solid ${accent}`,fontSize:72,lineHeight:1.18,fontWeight:1000,color:'#fff'}}>{hook}</div></div>:null}

    {cueActive&&frame>=hookEnd?<div style={{position:'absolute',left:cueInset,right:cueInset,bottom:Math.max(cueBottom,Number(props.captionProfile?.bottom??325)),zIndex:120,opacity:cueIn,transform:`translateX(${cueShift}px) scale(${.96+.04*cueIn})`}}><div style={{padding:cueIndex===1?'18px 30px 21px':'15px 25px 19px',borderRadius:cueIndex===2?12:24,background:cueFill,border:`3px solid ${cueIndex===1?'#fff':accent}`,fontSize:cueIndex===1?46:Math.min(50,Number(props.captionProfile?.fontSize??50)),lineHeight:1.22,fontWeight:1000,color:cueColor,textAlign:'center',boxShadow:'0 12px 34px rgba(0,0,0,.30)'}}>{messages[cueIndex]}</div></div>:null}

    {website&&frame>=websiteStart&&frame<websiteEnd?<AbsoluteFill style={{zIndex:160,background:'radial-gradient(circle at 50% 28%,rgba(244,180,0,.25),rgba(4,15,25,.98) 52%,#02070d 100%)'}}><div style={{position:'absolute',left:30,right:30,top:95,bottom:215,borderRadius:34,overflow:'hidden',background:'#fff',border:`4px solid ${accent}`,boxShadow:'0 18px 50px rgba(0,0,0,.38)'}}><div style={{height:76,background:'#081522',display:'flex',alignItems:'center',justifyContent:'center',fontSize:27,fontWeight:1000,color:'#fff',direction:'ltr'}}>KARYABMASHIN.IR</div><div style={{position:'absolute',left:0,right:0,top:76,bottom:0}}><OffthreadVideo src={website} playbackRate={1.45} muted volume={0} style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:'top center'}}/></div></div><div style={{position:'absolute',left:44,right:44,bottom:82,padding:'19px 24px',borderRadius:22,background:'#020B13',border:`3px solid ${accent}`,fontSize:48,fontWeight:1000,color:'#fff',textAlign:'center'}}>آگهی را در سایت واقعی ببین و بررسی کن</div></AbsoluteFill>:null}

    {frame>=endStart?<AbsoluteFill style={{zIndex:220,alignItems:'center',justifyContent:'center',padding:'110px 58px 130px',background:`radial-gradient(circle at 50% ${haloShift}%,rgba(244,180,0,.46),rgba(7,24,39,.985) 42%,#02070d 100%)`}}>
      <div style={{position:'absolute',top:0,left:0,right:0,height:10,background:accent}}/>
      <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:14,textAlign:'center',opacity:endOpacity,width:'100%',maxWidth:930}}>
        {logo?<Img src={logo} style={{width:230,height:230,objectFit:'contain',transform:`scale(${logoScale})`}}/>:null}
        <div style={{fontSize:82,lineHeight:1.05,fontWeight:1000,color:'#fff',opacity:brandOpacity}}>{brand}</div>
        <div style={{fontSize:33,fontWeight:900,color:'#fff',opacity:brandOpacity}}>بازار تخصصی خرید و فروش ماشین‌آلات</div>
        <div style={{marginTop:12,width:'100%',padding:'24px 34px 27px',borderRadius:28,background:accent,color:'#071827',fontSize:49,lineHeight:1.25,fontWeight:1000,boxShadow:'0 14px 40px rgba(0,0,0,.32)',opacity:ctaOpacity}}>{ctaAction}</div>
        <div style={{marginTop:3,fontSize:25,fontWeight:900,color:'#fff',opacity:siteOpacity}}>برای ثبت آگهی وارد سایت شو</div>
        <div style={{padding:'11px 24px',borderRadius:18,border:`3px solid ${accent}`,background:'rgba(2,11,19,.94)',fontSize:48,fontWeight:1000,color:accent,direction:'ltr',letterSpacing:.4,opacity:siteOpacity}}>{site}</div>
      </div>
    </AbsoluteFill>:null}
  </AbsoluteFill>;
};
