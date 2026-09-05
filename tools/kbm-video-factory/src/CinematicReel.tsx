import React from 'react';
import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import type {CaptionCue, CinematicAsset, CinematicScene, KbmVideoProps} from './types';

const safe = {bottom: 250, horizontal: 64};

const resolveSource = (src: string | null | undefined) => {
  if (!src) return null;
  if (/^(https?:|data:|file:)/i.test(src)) return src;
  return staticFile(src.replace(/^\/+/, ''));
};

const normalizeText = (value: string) =>
  value
    .replace(/[؟?!،,.؛:«»"'()\[\]{}]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();

const overlapsMeaningfully = (caption: string, scene: CinematicScene) => {
  const a = normalizeText(caption);
  const b = normalizeText([scene.title, scene.accentText, scene.kicker].filter(Boolean).join(' '));
  if (!a || !b) return false;
  return a === b || a.includes(b) || b.includes(a);
};

const transitionStyle = (scene: CinematicScene, frame: number, fps: number): React.CSSProperties => {
  const local = Math.max(0, frame - scene.from);
  const duration = Math.max(1, scene.to - scene.from);
  const outLocal = Math.max(0, scene.to - frame);
  const enterFrames = Math.min(Math.round(fps * 0.28), Math.max(4, Math.floor(duration / 3)));
  const exitFrames = Math.min(Math.round(fps * 0.20), Math.max(4, Math.floor(duration / 4)));
  const enter = interpolate(local, [0, enterFrames], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const exit = interpolate(outLocal, [0, exitFrames], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const visibility = Math.min(enter, exit);
  const kind = scene.transitionIn ?? 'fade';

  if (kind === 'push') return {opacity: visibility, transform: `translateX(${(1 - enter) * 90}px)`};
  if (kind === 'wipe') {
    return {opacity: visibility, clipPath: `inset(0 ${Math.max(0, 100 - enter * 100)}% 0 0)`};
  }
  if (kind === 'cross-zoom') return {opacity: visibility, transform: `scale(${1.12 - enter * 0.12})`};
  if (kind === 'flash') {
    return {
      opacity: visibility,
      filter: `brightness(${1 + (1 - enter) * 0.85})`,
      transform: `scale(${1.035 - enter * 0.035})`,
    };
  }
  if (kind === 'hard') return {opacity: 1};
  return {opacity: visibility};
};

const motionStyle = (scene: CinematicScene, frame: number): React.CSSProperties => {
  const local = Math.max(0, frame - scene.from);
  const span = Math.max(1, scene.to - scene.from);
  const progress = Math.min(1, local / span);
  switch (scene.motion) {
    case 'punch':
      return {transform: `scale(${1.06 - progress * 0.04})`};
    case 'slow-push':
      return {transform: `scale(${1 + progress * 0.045})`};
    case 'pan-left':
      return {transform: `scale(1.06) translateX(${-18 * progress}px)`};
    case 'pan-right':
      return {transform: `scale(1.06) translateX(${18 * progress}px)`};
    default:
      return {};
  }
};

const CaptionWords: React.FC<{cue: CaptionCue; frame: number; accent: string}> = ({cue, frame, accent}) => {
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
              textShadow: active ? `0 0 22px ${accent}` : '0 3px 14px rgba(0,0,0,.50)',
            }}
          >
            {word.text}
          </span>
        );
      })}
    </span>
  );
};

const SceneCopy: React.FC<{scene: CinematicScene; accent: string; frame: number; fps: number}> = ({
  scene,
  accent,
  frame,
  fps,
}) => {
  if (!scene.title && !scene.kicker && !scene.accentText && !scene.items?.length) return null;
  const local = Math.max(0, frame - scene.from);
  const enter = spring({frame: local, fps, config: {damping: 18, stiffness: 165, mass: 0.75}});
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: scene.kind === 'end-card' ? 'center' : 'flex-end',
        padding: scene.kind === 'end-card' ? '180px 86px 240px' : '0 72px 350px',
        direction: 'rtl',
        textAlign: 'right',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          transform: `translateY(${(1 - enter) * 42}px) scale(${0.97 + enter * 0.03})`,
          opacity: enter,
          maxWidth: 920,
          margin: scene.kind === 'end-card' ? '0 auto' : 0,
          textAlign: scene.kind === 'end-card' ? 'center' : 'right',
        }}
      >
        {scene.kicker ? (
          <div
            style={{
              display: 'inline-block',
              border: `1px solid ${accent}`,
              color: accent,
              background: 'rgba(11,31,51,.68)',
              borderRadius: 999,
              padding: '9px 18px',
              fontSize: 26,
              fontWeight: 900,
              marginBottom: 18,
            }}
          >
            {scene.kicker}
          </div>
        ) : null}
        {scene.title ? (
          <div
            style={{
              color: '#fff',
              fontSize: scene.kind === 'end-card' ? 74 : 62,
              lineHeight: 1.25,
              fontWeight: 950,
              textShadow: '0 10px 34px rgba(0,0,0,.66)',
            }}
          >
            {scene.title}
          </div>
        ) : null}
        {scene.accentText ? (
          <div
            style={{
              color: accent,
              fontSize: scene.kind === 'end-card' ? 42 : 36,
              lineHeight: 1.5,
              fontWeight: 900,
              marginTop: 12,
              textShadow: '0 5px 24px rgba(0,0,0,.62)',
            }}
          >
            {scene.accentText}
          </div>
        ) : null}
        {scene.items?.length ? (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${Math.min(3, scene.items.length)}, 1fr)`,
              gap: 16,
              marginTop: 28,
            }}
          >
            {scene.items.map((item, index) => (
              <div
                key={`${item.label}-${index}`}
                style={{
                  padding: '22px 16px',
                  background: 'linear-gradient(145deg, rgba(11,31,51,.92), rgba(23,50,77,.82))',
                  border: '1px solid rgba(244,180,0,.55)',
                  boxShadow: '0 16px 40px rgba(0,0,0,.30)',
                  textAlign: 'center',
                  clipPath: 'polygon(5% 0,100% 0,100% 85%,95% 100%,0 100%,0 15%)',
                }}
              >
                <div style={{color: '#fff', fontSize: 31, fontWeight: 950}}>{item.label}</div>
                {item.value ? (
                  <div style={{color: accent, fontSize: 22, marginTop: 8, fontWeight: 800}}>{item.value}</div>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
};

export const CinematicReel: React.FC<KbmVideoProps> = ({
  media,
  captions = [],
  scenes = [],
  assets = [],
  accent = '#F4B400',
  background = '#0B1F33',
  muted = true,
  volume = 1,
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const mediaSource = resolveSource(media);
  const activeScene = scenes.find((scene) => frame >= scene.from && frame < scene.to);
  const assetMap = new Map<string, CinematicAsset>(assets.map((asset) => [asset.id, asset]));
  const sceneAsset = activeScene?.assetId ? assetMap.get(activeScene.assetId) : undefined;
  const sceneSource = resolveSource(sceneAsset?.src);
  const currentCaption = captions.find((cue) => frame >= cue.from && frame <= cue.to);
  const captionSuppressed =
    Boolean(activeScene?.suppressCaption) ||
    Boolean(currentCaption && activeScene && overlapsMeaningfully(currentCaption.text, activeScene));
  const progress = Math.max(0, Math.min(1, frame / Math.max(1, durationInFrames - 1)));

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
        <AbsoluteFill>
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
            ? 'linear-gradient(180deg, rgba(11,31,51,.10) 0%, rgba(11,31,51,.00) 45%, rgba(11,31,51,.58) 100%)'
            : `linear-gradient(145deg, ${background}, #17324D)`,
        }}
      />

      {activeScene && sceneSource && sceneAsset?.kind === 'image' ? (
        <AbsoluteFill style={transitionStyle(activeScene, frame, fps)}>
          <AbsoluteFill style={motionStyle(activeScene, frame)}>
            <Img src={sceneSource} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
          </AbsoluteFill>
          <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(5,15,25,.04), rgba(5,15,25,.26))'}} />
        </AbsoluteFill>
      ) : null}

      {activeScene && !sceneSource && activeScene.kind !== 'video' ? (
        <AbsoluteFill
          style={{
            ...transitionStyle(activeScene, frame, fps),
            background: 'linear-gradient(145deg, rgba(11,31,51,.96), rgba(23,50,77,.88))',
          }}
        />
      ) : null}

      {activeScene ? <SceneCopy scene={activeScene} accent={accent} frame={frame} fps={fps} /> : null}

      {currentCaption && !captionSuppressed ? (
        <div
          style={{
            position: 'absolute',
            left: safe.horizontal,
            right: safe.horizontal,
            bottom: safe.bottom,
            display: 'flex',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              maxWidth: 920,
              fontSize: 46,
              lineHeight: 1.52,
              fontWeight: 900,
              textAlign: 'center',
              background: 'rgba(2,12,22,.72)',
              borderRight: `5px solid ${accent}`,
              padding: '17px 26px',
              boxShadow: '0 16px 50px rgba(0,0,0,.32)',
            }}
          >
            <CaptionWords cue={currentCaption} frame={frame} accent={accent} />
          </div>
        </div>
      ) : null}

      <div
        style={{
          position: 'absolute',
          left: safe.horizontal,
          right: safe.horizontal,
          bottom: 132,
          height: 4,
          background: 'rgba(255,255,255,.14)',
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
    </AbsoluteFill>
  );
};
