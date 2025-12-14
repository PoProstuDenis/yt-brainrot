"""Monta7C wideo: łączy obraz (lub video) i audio w pionowy short 1080x1920 przy pomocy ffmpeg.
"""
import subprocess
from pathlib import Path
import json


def get_audio_duration(audio_path: str) -> float:
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', audio_path
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
        out = p.stdout
        j = json.loads(out)
        return float(j['format']['duration'])
    except Exception:
        return 30.0


def create_short_from_image(image_path: str, audio_path: str, out_path: str,
                            width: int = 1080, height: int = 1920) -> str:
    """Create a short by combining image and audio.

    `width`/`height` specify target video resolution. For downsizing workflow,
    pass 720x1280 here and then upscale the resulting video.
    """
    image_path = str(image_path)
    audio_path = str(audio_path)
    out_path = str(out_path)
    duration = get_audio_duration(audio_path)

    vf = (
        f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
        f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p'
    )

    cmd = [
        'ffmpeg', '-y', '-loop', '1', '-i', image_path, '-i', audio_path,
        '-c:v', 'libx264', '-t', str(duration), '-r', '30',
        '-vf', vf,
        '-c:a', 'aac', '-b:a', '192k', '-shortest', out_path
    ]
    subprocess.run(cmd, check=True)
    return out_path


def upscale_video_to_1080x1920(input_video: str, out_path: str) -> str:
    """Upscale a video (preserving aspect) to 1080x1920 using lanczos filter.

    This is a fast, free upscaler. For better quality use ESRGAN/Real-ESRGAN.
    """
    cmd = [
        'ffmpeg', '-y', '-i', input_video,
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
        '-vf', 'scale=1080:1920:flags=lanczos,format=yuv420p',
        '-c:a', 'copy', out_path
    ]
    subprocess.run(cmd, check=True)
    return out_path


if __name__ == '__main__':
    print(create_short_from_image('out_bg.jpg', 'out.wav', 'out_short.mp4'))
