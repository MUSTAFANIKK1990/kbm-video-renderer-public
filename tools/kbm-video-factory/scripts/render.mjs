#!/usr/bin/env node

import {existsSync, mkdirSync, readFileSync, rmSync, writeFileSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');

const args = process.argv.slice(2);
const getArg = (name, fallback = null) => {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};

const template = getArg('--template', 'KBM-V03-MACHINE-REVIEW');
const input = getArg('--input');
const out = resolve(process.cwd(), getArg('--out', './out/reel.mp4'));
const requestedDuration = Number.parseInt(getArg('--duration-frames', '0'), 10);

const allowed = new Set([
  'KBM-V01-INFOGRAPHIC',
  'KBM-V02-PRESENTER-UI',
  'KBM-V03-MACHINE-REVIEW',
  'KBM-V04-MOTION-POSTER',
  'KBM-V05-TECHNICAL-VFX',
  'KBM-V06-STORY-REVEAL',
]);

if (!allowed.has(template)) {
  console.error(`Unknown template: ${template}`);
  process.exit(2);
}

let props = {templateId: template, title: 'کاریاب ماشین'};
if (input) {
  const inputPath = resolve(process.cwd(), input);
  if (!existsSync(inputPath)) {
    console.error(`Input JSON not found: ${inputPath}`);
    process.exit(2);
  }
  props = {...JSON.parse(readFileSync(inputPath, 'utf8')), templateId: template};
}

const propsDuration = Number.parseInt(String(props.durationInFrames ?? 0), 10);
const durationInFrames = requestedDuration > 0 ? requestedDuration : propsDuration;
if (durationInFrames > 1800) {
  console.error('Package 02 supports a maximum of 1800 frames (60 seconds at 30 fps).');
  process.exit(2);
}
if (durationInFrames > 0) {
  props.durationInFrames = durationInFrames;
}

mkdirSync(dirname(out), {recursive: true});
const tmpDir = resolve(root, '.tmp');
mkdirSync(tmpDir, {recursive: true});
const propsFile = resolve(tmpDir, `props-${Date.now()}.json`);
writeFileSync(propsFile, JSON.stringify(props, null, 2), 'utf8');

const command = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const renderArgs = [
  'remotion',
  'render',
  'src/index.ts',
  template,
  out,
  `--props=${propsFile}`,
  '--codec=h264',
  '--pixel-format=yuv420p',
];

if (durationInFrames > 0) {
  renderArgs.push(`--frames=0-${durationInFrames - 1}`);
}

const result = spawnSync(command, renderArgs, {cwd: root, stdio: 'inherit'});
rmSync(propsFile, {force: true});
process.exit(result.status ?? 1);