import React from 'react';
import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import type {CaptionCue, CreativeOverlay, KbmVideoProps} from './types';

const safe = {
  top: 150,
  bottom: 250,
  horizontal: 64,
};

const clamp = (value: number, min = 0, max = 1) => Math.max(min, Math.min(max, value));

const patternMotion = (templateId: string, frame: number) => {
  switch (templateId) {
    case 'KBM-V01-INFOGRAPHIC':
      return {scale: interpolate(frame, [0, 20], [0.94, 1], {extrapolateRight: 'clamp'}), rotate: 0};
    case 'KBM-V02-PRESENTER-UI':
      return {scale: interpolate(frame, [0, 16], [1.06, 1], {extrapolateRight: 'clamp'}), rotate: 0};
    case 'KBM-V04-MOTION-POSTER':
      return {scale: interpolate(frame, [0, 36], [1.12, 1], {extrapolateRight: 'clamp'}), rotate: 0};
    case 'KBM-V05-TECHNICAL-VFX':
      return {scale: 1, rotate: interpolate(frame, [0, 8, 16], [-0.5, 0.5, 0], {extrapolateRight: 'clamp'})};
    case 'KBM-V06-STORY-REVEAL':
      return {scale: interpolate(frame, [0, 12], [1.08, 1], {extrapolateRight: 'clamp'}), rotate: 0};
    default:
      return {scale: interpolate(frame, [0, 20], [1.035, 1], {extrapolateRight: 'clamp'}), rotate: 0};
  }
};

const resolveMediaSource = (media: string | null | undefined) => {
  if (!media) return null;
  if (/^(https?:|data:|file:)/i.test(media)) return media;
  return staticFile(media.replace(/^\/+/, ''));
};

const CaptionText: React.FC<{cue: CaptionCue; frame: number; accent: string}> = ({cue, frame, accent}) => {
  if (!cue.words?.length) return <>{cue.text}</>;

  return (
    <span style={{display: 'inline-flex', flexWrap: 'wrap', justifyContent: 'center', gap: '0 12px'}}>
      {cue.words.map((word, index) => {
        const active = frame >= word.from && frame <= word.to;
        return (
          <span
            key={`${word.from}-${word.to}-${index}`}
            style={{
              color: active ? accent : '#fff',
              transform: active ? 'scale(1.08) translateY(-2px)' : 'scale(1)',
              textShadow: active ? `0 0 24px ${accent}` : '0 3px 14px rgba(0,0,0,.45)',
            }}
          >
            {word.text}
          </span>
        );
      })}
    </span>
  );
};

const overlayTop = (overlay: CreativeOverlay) => {
  if (overlay.position === 'top') return 250;
  if (overlay.position === 'center') return 650;
  return 1090;
};

const pointNumber = (overlay: CreativeOverlay) => {
  if (overlay.kind !== 'point') return null;
  const match = (overlay.eyebrow || '').match(/[123۱۲۳]/);
  if (!match) return null;
  const map: Record<string, string> = {1: '۰۱', 2: '۰۲', 3: '۰۳', '۱': '۰۱', '۲': '۰۲', '۳': '۰۳'};
  return map[match[0]] || null;
};

const CornerHud: React.FC<{accent: string; frame: number}> = ({accent, frame}) => {
  const breathe = 0.45 + 0.18 * Math.sin(frame / 13);
  const common = {position: 'absolute' as const, width: 68, height: 68, opacity: breathe};
  const edge = `3px solid ${accent}`;
  return (
    <>
      <div style={{...common, top: 92, left: 52, borderTop: edge, borderLeft: edge}} />
      <div style={{...common, top: 92, right: 52, borderTop: edge, borderRight: edge}} />
      <div style={{...common, bottom: 120, left: 52, borderBottom: edge, borderLeft: edge}} />
      <div style={{...common, bottom: 120, right: 52, borderBottom: edge, borderRight: edge}} />
    </>
  );
};

const CreativeCard: React.FC<{
  overlay: CreativeOverlay;
  frame: number;
  fps: number;
  accent: string;
  background: string;
}> = ({overlay, frame, fps, accent, background}) => {
  const local = Math.max(0, frame - overlay.from);
  const enter = spring({frame: local, fps, config: {damping: 18, stiffness: 180, mass: 0.72}});
  const exit = interpolate(frame, [Math.max(overlay.from, overlay.to - 12), overlay.to], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const reveal = interpolate(local, [0, 14], [0, 1], {extrapolateRight: 'clamp'});
  const accentSweep = interpolate(local, [4, 18], [0, 1], {extrapolateRight: 'clamp'});
  const isHook = overlay.kind === 'hook';
  const isCta = overlay.kind === 'cta';
  const number = pointNumber(overlay);
  const top = overlayTop(overlay);
  const translateX = interpolate(enter, [0, 1], [isHook ? 100 : 72, 0]);
  const translateY = interpolate(enter, [0, 1], [42, 0]);
  const blur = interpolate(enter, [0, 1], [14, 0]);
  const skew = interpolate(enter, [0, 1], [-2.4, 0]);

  return (
    <div
      style={{
        position: 'absolute',
        top,
        left: safe.horizontal,
        right: safe.horizontal,
        opacity: enter * exit,
        transform: `translate(${translateX}px, ${translateY}px) scale(${interpolate(enter, [0, 1], [0.965, 1])}) skewX(${skew}deg)`,
        filter: `blur(${blur}px)`,
        display: 'flex',
        justifyContent: isCta ? 'center' : 'flex-start',
      }}
    >
      <div
        style={{
          width: isCta ? '92%' : isHook ? '96%' : '88%',
          minHeight: isHook ? 280 : isCta ? 320 : 255,
          position: 'relative',
          overflow: 'hidden',
          background: isCta
            ? 'linear-gradient(135deg, rgba(11,31,51,.97), rgba(19,49,75,.90))'
            : 'linear-gradient(135deg, rgba(4,15,26,.88), rgba(15,36,55,.70))',
          clipPath: isCta
            ? 'polygon(5% 0, 100% 0, 100% 82%, 95% 100%, 0 100%, 0 18%)'
            : 'polygon(0 0, 94% 0, 100% 18%, 100% 100%, 6% 100%, 0 82%)',
          border: '1px solid rgba(255,255,255,.16)',
          boxShadow: '0 28px 85px rgba(0,0,0,.46)',
          backdropFilter: 'blur(16px)',
          padding: isCta ? '42px 46px' : isHook ? '34px 38px' : '30px 34px 28px',
          textAlign: isCta ? 'center' : 'right',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 0,
            right: 0,
            width: `${Math.max(6, 100 * accentSweep)}%`,
            height: 6,
            background: `linear-gradient(90deg, transparent, ${accent})`,
            boxShadow: `0 0 28px ${accent}`,
          }}
        />

        <div
          style={{
            position: 'absolute',
            inset: 0,
            transform: `translateX(${interpolate(reveal, [0, 1], [100, -130])}%)`,
            background: 'linear-gradient(100deg, transparent 20%, rgba(255,255,255,.11) 48%, transparent 74%)',
            pointerEvents: 'none',
          }}
        />

        {number ? (
          <div
            style={{
              position: 'absolute',
              left: 20,
              top: -30,
              fontSize: 190,
              fontWeight: 950,
              lineHeight: 1,
              letterSpacing: -12,
              color: accent,
              opacity: 0.13,
              transform: `scale(${interpolate(enter, [0, 1], [1.18, 1])})`,
            }}
          >
            {number}
          </div>
        ) : null}

        <div style={{position: 'relative', zIndex: 2}}>
          {overlay.eyebrow ? (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 10,
                color: isCta ? background : accent,
                background: isCta ? accent : 'rgba(244,180,0,.10)',
                border: `1px solid ${accent}`,
                fontSize: isCta ? 28 : 25,
                fontWeight: 950,
                borderRadius: 999,
                padding: '9px 18px',
                marginBottom: 20,
                boxShadow: isCta ? '0 0 30px rgba(244,180,0,.24)' : undefined,
              }}
            >
              <span style={{width: 8, height: 8, borderRadius: 999, background: isCta ? background : accent}} />
              {overlay.eyebrow}
            </div>
          ) : null}

          <div
            style={{
              maxWidth: isCta ? 860 : 820,
              marginRight: isCta ? 'auto' : 0,
              marginLeft: isCta ? 'auto' : 0,
              fontSize: isHook ? 70 : isCta ? 58 : 52,
              lineHeight: 1.32,
              fontWeight: 950,
              color: '#fff',
              textShadow: '0 5px 22px rgba(0,0,0,.52)',
              transform: `translateX(${interpolate(reveal, [0, 1], [26, 0])}px)`,
            }}
          >
            {overlay.text}
          </div>

          {overlay.accentText ? (
            <div
              style={{
                position: 'relative',
                display: 'inline-flex',
                marginTop: 18,
                maxWidth: isCta ? 820 : 760,
                padding: '10px 18px 10px 22px',
                fontSize: isHook ? 42 : isCta ? 31 : 31,
                lineHeight: 1.55,
                fontWeight: 850,
                color: isCta ? '#fff' : accent,
                background: isCta ? 'rgba(255,255,255,.07)' : 'rgba(244,180,0,.08)',
                borderRight: `5px solid ${accent}`,
                transform: `translateX(${interpolate(reveal, [0, 1], [38, 0])}px)`,
              }}
            >
              {overlay.accentText}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export const KbmReel: React.FC<KbmVideoProps> = ({
  templateId,
  title,
  subtitle,
  cta = 'مشاهده در کاریاب ماشین',
  accent = '#F4B400',
  background = '#0B1F33',
  media,
  captions = [],
  overlays = [],
  muted = true,
  volume = 1,
  introFrames = 150,
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const intro = spring({frame, fps, config: {damping: 16, stiffness: 120}});
  const motion = patternMotion(templateId, frame);
  const currentCaption = captions.find((cue) => frame >= cue.from && frame <= cue.to);
  const activeOverlays = overlays.filter((overlay) => frame >= overlay.from && frame <= overlay.to);
  const activeOverlay = activeOverlays[0];
  const mediaSource = resolveMediaSource(media);
  const creativeMode = overlays.length > 0;
  const ctaOverlayActive = activeOverlays.some((overlay) => overlay.kind === 'cta');
  const activeLocal = activeOverlay ? Math.max(0, frame - activeOverlay.from) : 999;
  const punch = activeOverlay
    ? interpolate(activeLocal, [0, 6, 18], [0.028, 0.01, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      })
    : 0;
  const flash = activeOverlay
    ? interpolate(activeLocal, [0, 3, 10], [0.26, 0.12, 0], {extrapolateRight: 'clamp'})
    : 0;
  const introFade = interpolate(
    frame,
    [Math.max(0, introFrames - 24), Math.max(1, introFrames)],
    [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );
  const progress = clamp(frame / Math.max(1, durationInFrames - 1));
  const scanY = ((frame * 5) % 2100) - 100;

  return (
    <AbsoluteFill
      style={{
        background,
        color: '#fff',
        direction: 'rtl',
        fontFamily: 'Estedad, Noto Sans Arabic, Arial, sans-serif',
        overflow: 'hidden',
      }}
    >
      {mediaSource ? (
        <AbsoluteFill
          style={{
            transform: `scale(${motion.scale + punch}) rotate(${motion.rotate}deg) translate(${2 * Math.sin(frame / 19)}px, ${2 * Math.cos(frame / 23)}px)`,
            filter: 'contrast(1.055) saturate(1.08)',
          }}
        >
          <OffthreadVideo
            src={mediaSource}
            muted={muted}
            volume={Math.max(0, Math.min(1, volume))}
            style={{width: '100%', height: '100%', objectFit: 'cover'}}
          />
        </AbsoluteFill>
      ) : null}

      <AbsoluteFill
        style={{
          background: mediaSource
            ? 'linear-gradient(180deg, rgba(11,31,51,.22) 0%, rgba(11,31,51,.01) 38%, rgba(11,31,51,.70) 100%)'
            : `linear-gradient(145deg, ${background} 0%, #17324D 100%)`,
        }}
      />

      {creativeMode ? (
        <>
          <AbsoluteFill
            style={{
              opacity: 0.08,
              backgroundImage:
                'repeating-linear-gradient(0deg, transparent 0px, transparent 5px, rgba(255,255,255,.16) 6px)',
            }}
          />
          <div
            style={{
              position: 'absolute',
              top: scanY,
              left: 0,
              right: 0,
              height: 2,
              opacity: 0.18,
              background: `linear-gradient(90deg, transparent, ${accent}, transparent)`,
              boxShadow: `0 0 18px ${accent}`,
            }}
          />
          <AbsoluteFill
            style={{
              opacity: flash,
              background: `radial-gradient(circle at 70% 45%, ${accent} 0%, rgba(244,180,0,.08) 28%, transparent 62%)`,
            }}
          />
          <CornerHud accent={accent} frame={frame} />
          <div
            style={{
              position: 'absolute',
              top: 116,
              right: safe.horizontal,
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              background: 'rgba(6,20,33,.82)',
              border: '1px solid rgba(244,180,0,.65)',
              clipPath: 'polygon(0 0, 88% 0, 100% 50%, 88% 100%, 0 100%)',
              padding: '11px 28px 11px 20px',
              fontSize: 25,
              fontWeight: 950,
              boxShadow: '0 14px 34px rgba(0,0,0,.34)',
            }}
          >
            <span style={{color: accent}}>●</span>
            کاریاب ماشین
          </div>
        </>
      ) : null}

      {!creativeMode ? (
        <div
          style={{
            position: 'absolute',
            top: safe.top,
            left: safe.horizontal,
            right: safe.horizontal,
            opacity: intro * introFade,
            transform: `translateY(${interpolate(intro, [0, 1], [36, 0])}px)`,
          }}
        >
          <div
            style={{
              display: 'inline-block',
              background: accent,
              color: '#0B1F33',
              fontSize: 30,
              fontWeight: 900,
              borderRadius: 999,
              padding: '12px 24px',
              marginBottom: 28,
            }}
          >
            کاریاب ماشین
          </div>
          <div style={{fontSize: 74, lineHeight: 1.25, fontWeight: 900, textShadow: '0 4px 24px rgba(0,0,0,.28)'}}>
            {title}
          </div>
          {subtitle ? (
            <div style={{fontSize: 40, lineHeight: 1.5, fontWeight: 600, color: '#E6EDF4', marginTop: 18}}>
              {subtitle}
            </div>
          ) : null}
        </div>
      ) : null}

      {activeOverlays.map((overlay, index) => (
        <CreativeCard
          key={`${overlay.from}-${overlay.to}-${overlay.kind}-${index}`}
          overlay={overlay}
          frame={frame}
          fps={fps}
          accent={accent}
          background={background}
        />
      ))}

      {currentCaption && !activeOverlays.some((overlay) => overlay.position === 'bottom') ? (
        <div
          style={{
            position: 'absolute',
            left: safe.horizontal,
            right: safe.horizontal,
            bottom: safe.bottom + 160,
            display: 'flex',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              maxWidth: 900,
              fontSize: 47,
              lineHeight: 1.55,
              fontWeight: 900,
              textAlign: 'center',
              background: 'rgba(2,12,22,.72)',
              borderRight: `5px solid ${accent}`,
              padding: '18px 28px',
              boxShadow: '0 16px 50px rgba(0,0,0,.32)',
            }}
          >
            <CaptionText cue={currentCaption} frame={frame} accent={accent} />
          </div>
        </div>
      ) : null}

      {creativeMode ? (
        <>
          <div
            style={{
              position: 'absolute',
              left: safe.horizontal,
              right: safe.horizontal,
              bottom: 135,
              height: 5,
              background: 'rgba(255,255,255,.16)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${progress * 100}%`,
                height: '100%',
                background: accent,
                boxShadow: `0 0 18px ${accent}`,
              }}
            />
          </div>
          <div
            style={{
              position: 'absolute',
              bottom: 90,
              left: safe.horizontal,
              color: 'rgba(255,255,255,.72)',
              fontSize: 22,
              fontWeight: 800,
              letterSpacing: 1.2,
            }}
          >
            KARYABMASHIN.IR
          </div>
        </>
      ) : null}

      {!creativeMode && !ctaOverlayActive ? (
        <div
          style={{
            position: 'absolute',
            left: safe.horizontal,
            right: safe.horizontal,
            bottom: safe.bottom,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 24,
            padding: '24px 30px',
            borderRadius: 30,
            background: 'rgba(11,31,51,.92)',
            border: '1px solid rgba(255,255,255,.14)',
            boxShadow: '0 18px 55px rgba(0,0,0,.3)',
          }}
        >
          <div style={{fontSize: 32, fontWeight: 800}}>karyabmashin.ir</div>
          <div
            style={{
              background: accent,
              color: '#0B1F33',
              fontSize: 32,
              fontWeight: 900,
              borderRadius: 22,
              padding: '15px 22px',
            }}
          >
            {cta}
          </div>
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
