import os
import sys
from pathlib import Path
import pytest
# Ensure project package is importable during tests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yt_brainrot import publisher


def test_publish_raises_when_env_missing(tmp_path):
    # Ensure POSTIZ env vars are not set
    os.environ.pop('POSTIZ_API_URL', None)
    os.environ.pop('POSTIZ_API_KEY', None)

    video = tmp_path / "video.mp4"
    video.write_bytes(b"dummy")

    with pytest.raises(RuntimeError):
        publisher.publish_to_postiz(str(video), "t", "d", ["a", "b"]) 
