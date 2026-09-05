import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {CinematicReelResolved} from './CinematicReelResolved';
import {Package13BrandLayer} from './Package13BrandLayer';
import type {CinematicScene, KbmVideoProps} from './types';

const transitionOverlay = (
  scene: CinematicScene | undefined,
  frame: number,
  fps: number,
  accent: string,
): React.ReactNode => {
  if (!scene || frame < scene.from) return null;
  const local = frame - scene.from;
  const window = Math.max(5, Math.round(fps * 0.34));
  if (local > window) return null;

  const progress = interpolate(local, [0, window], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const fade = 1 - progress;
  const kind = scene.transitionIn ?? 'fade';

  if (kind === 'flash') {
    return (
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at 50% 46%, rgba(255,255,255,${0.82 * fade}) 0%, rgba(244,180,0,${0.34 * fade}) 28%, rgba(244,180,0,0) 72%)`,
          mixBlendMode: 'screen',
          pointerEvents: 'none',
        }}
      />
    );
  }

  if (kind === 'push') {
    return (
      <AbsoluteFill style={{pointerEvents: 'none', overflow: 'hidden'}}>
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            width: 118,
            right: 0,
            background: `linear-gradient(90deg, rgba(244,180,0,0), ${accent}, rgba(255,255,255,.82), rgba(244,180,0,0))`,
            transform: `translateX(${-1180 * progress}px) skewX(-8deg)`,
            opacity: Math.min(1, fade * 1.25),
            filter: 'blur(2px)',
            boxShadow: `0 0 52px ${accent}`,
          }}
        />
      </AbsoluteFill>
    );
  }

  if (kind === 'cross-zoom') {
    return (
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at center, rgba(244,180,0,${0.22 * fade}) 0%, rgba(255,255,255,${0.10 * fade}) 18%, rgba(11,31,51,0) 62%)`,
          transform: `scale(${0.82 + progress * 0.28})`,
          mixBlendMode: 'screen',
          pointerEvents: 'none',
        }}
      />
    );
  }

  if (kind === 'wipe') {
    return (
      <AbsoluteFill
        style={{
          background: `linear-gradient(90deg, rgba(11,31,51,0) 0%, rgba(244,180,0,${0.34 * fade}) 50%, rgba(255,255,255,${0.16 * fade}) 56%, rgba(11,31,51,0) 100%)`,
          transform: `translateX(${(progress - 0.5) * 1180}px)`,
          pointerEvents: 'none',
        }}
      />
    );
  }

  if (kind === 'hard') {
    return (
      <AbsoluteFill
        style={{
          border: `${Math.max(0, Math.round(14 * fade))}px solid rgba(244,180,0,${0.24 * fade})`,
          boxShadow: `inset 0 0 ${Math.round(80 * fade)}px rgba(244,180,0,${0.13 * fade})`,
          pointerEvents: 'none',
        }}
      />
    );
  }

  return null;
};

export const CinematicPolishedReel: React.FC<KbmVideoProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = props.accent ?? '#F4B400';
  const scenes = props.scenes ?? [];
  const activeScene = scenes.find((scene) => frame >= scene.from && frame < scene.to);
  const grainOpacity = 0.035 + ((Math.sin(frame * 1.618) + 1) / 2) * 0.018;

  return (
    <AbsoluteFill style={{background: props.background ?? '#0B1F33'}}>
      <AbsoluteFill
        style={{
          filter: 'contrast(1.075) saturate(1.055) brightness(.965)',
        }}
      >
        <CinematicReelResolved {...props} />
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          background:
            'linear-gradient(180deg, rgba(5,16,28,.17) 0%, rgba(11,31,51,.015) 34%, rgba(244,180,0,.025) 68%, rgba(3,10,18,.19) 100%)',
          mixBlendMode: 'soft-light',
          pointerEvents: 'none',
        }}
      />

      <AbsoluteFill
        style={{
          boxShadow: 'inset 0 0 185px rgba(0,0,0,.43)',
          pointerEvents: 'none',
        }}
      />

      <AbsoluteFill
        style={{
          background:
            'repeating-radial-gradient(circle at 17% 23%, rgba(255,255,255,.18) 0 1px, rgba(0,0,0,.20) 1px 2px, transparent 2px 4px)',
          backgroundSize: '7px 7px',
          opacity: grainOpacity,
          mixBlendMode: 'overlay',
          transform: `translate(${(frame % 3) - 1}px, ${((frame * 2) % 3) - 1}px)`,
          pointerEvents: 'none',
        }}
      />

      {transitionOverlay(activeScene, frame, fps, accent)}

      <Package13BrandLayer {...props} />
    </AbsoluteFill>
  );
};
