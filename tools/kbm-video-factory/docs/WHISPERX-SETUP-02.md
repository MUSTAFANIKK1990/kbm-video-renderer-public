# WhisperX Setup — Package 02

WhisperX is optional at repository install time but required for automatic Persian caption generation.

## Recommended isolated Python environment

```bash
python -m venv .venv-whisperx
```

Activate the environment and install WhisperX from PyPI:

```bash
pip install whisperx
```

The KBM adapter deliberately does not vendor model weights or Python dependencies into this repository.

## Runtime profiles

`pipeline/whisperx_adapter.py` automatically chooses a conservative profile:

- NVIDIA GPU detected: `large-v3` + `cuda` + `float16`
- No NVIDIA GPU: `small` + `cpu` + `int8`

Override with CLI flags or environment variables:

```bash
KBM_WHISPERX_MODEL=large-v3
KBM_WHISPERX_DEVICE=cuda
KBM_WHISPERX_COMPUTE_TYPE=float16
```

Equivalent CLI:

```bash
python pipeline/whisperx_adapter.py \
  --input ./public/generated/demo/media.mp4 \
  --output-dir ./work/demo/whisperx \
  --language fa \
  --model large-v3 \
  --device cuda \
  --compute-type float16
```

## Important operational note

WhisperX alignment support is language/model dependent. Package 02 does not invent or silently repair missing word timestamps. If a segment has no aligned word timings, `pipeline/captions.py` falls back to segment-level timing for that content.

## Dry-run

Use this to inspect the exact command without model execution:

```bash
python pipeline/whisperx_adapter.py \
  --input ./public/generated/demo/media.mp4 \
  --output-dir ./work/demo/whisperx \
  --language fa \
  --dry-run
```
