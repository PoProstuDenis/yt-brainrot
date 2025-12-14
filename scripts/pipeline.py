"""Główny pipeline: generuj story, TTS, obraz, montuj short i (opcjonalnie) publikuj.

U7Cżycie:
  python scripts/pipeline.py --count 3 --outdir outputs --publish
"""
import argparse
import os
from pathlib import Path
from yt_brainrot import llm, tts, visual, editor, publisher
from yt_brainrot import sd_a1111
import time


def make_dirs(base: Path):
    for d in ['input', 'audio', 'images', 'videos', 'publish']:
        (base / d).mkdir(parents=True, exist_ok=True)


def build_metadata(text: str) -> tuple[str, str, list[str]]:
    # Simple clickbait title + description + tags
    title = (text.split('.')[0] + '...').strip()[:70]
    description = text + '\n\n#brainrot #shorts'
    tags = ['brainrot', 'shorts', 'viral']
    return title, description, tags


def run_once(outdir: Path, index: int, publish: bool = False):
    prompt = None
    story = llm.generate_story(prompt)
    print(f'LLM -> {story}')

    audio_path = outdir / 'audio' / f'audio_{index}.wav'
    tts.tts_to_wav(story, str(audio_path))
    print('TTS generated:', audio_path)

    image_path = outdir / 'images' / f'bg_{index}.jpg'
    # Generate at 720x1280 then upscale to 1080x1920 later to save VRAM
    small_size = (720, 1280)
    try:
        if sd_a1111.is_server_alive():
            print('A1111 server detected — generating via A1111 (720x1280)')
            sd_a1111.generate_image_a1111(story, str(image_path), width=small_size[0], height=small_size[1])
        else:
            raise RuntimeError('A1111 not available')
    except Exception:
        print('A1111 not available — using fallback visual generator (PIL)')
        visual.create_background_from_prompt(story, str(image_path), size=small_size)
    print('Image generated:', image_path)

    # Create video at small resolution first
    small_video = outdir / 'videos' / f'short_small_{index}.mp4'
    editor.create_short_from_image(str(image_path), str(audio_path), str(small_video), width=small_size[0], height=small_size[1])
    print('Small video created:', small_video)

    # Upscale to final 1080x1920
    final_video = outdir / 'videos' / f'short_{index}.mp4'
    editor.upscale_video_to_1080x1920(str(small_video), str(final_video))
    print('Upscaled final video:', final_video)

    title, description, tags = build_metadata(story)
    if publish:
        try:
            res = publisher.publish_to_postiz(str(final_video), title, description, tags)
            print('Published:', res)
        except Exception as e:
            print('Publish failed (configure Postiz):', e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=1)
    parser.add_argument('--outdir', type=str, default='outputs')
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()

    base = Path(args.outdir)
    make_dirs(base)

    for i in range(args.count):
        run_once(base, i + 1, publish=args.publish)
        time.sleep(1)


if __name__ == '__main__':
    main()
