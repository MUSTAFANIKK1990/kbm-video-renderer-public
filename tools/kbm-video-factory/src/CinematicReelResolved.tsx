import React from 'react';
import {CinematicReel} from './CinematicReel';
import type {KbmVideoProps} from './types';

/**
 * Approved Package 10 image assets already contain their designed Persian copy.
 * When an image asset resolves successfully, strip the procedural SceneCopy fields
 * so captions/headlines are not rendered twice. If the asset is missing, keep the
 * copy intact so the non-blocking static-card fallback remains informative.
 */
export const CinematicReelResolved: React.FC<KbmVideoProps> = (props) => {
  const resolvedImageIds = new Set(
    (props.assets ?? [])
      .filter((asset) => asset.kind === 'image' && Boolean(asset.src))
      .map((asset) => asset.id),
  );

  const scenes = (props.scenes ?? []).map((scene) => {
    if (!scene.assetId || !resolvedImageIds.has(scene.assetId)) return scene;
    return {
      ...scene,
      title: undefined,
      kicker: undefined,
      accentText: undefined,
      items: [],
    };
  });

  return <CinematicReel {...props} scenes={scenes} />;
};
