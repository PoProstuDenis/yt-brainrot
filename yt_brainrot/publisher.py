"""Szkic publikatora przez Postiz.

U7Cytkownik musi ustawić POSTIZ_API_URL i POSTIZ_API_KEY w zmiennych srodowiskowych.
"""
import os
import requests


def publish_to_postiz(video_path: str, title: str, description: str, tags: list[str]) -> dict:
    url = os.environ.get('POSTIZ_API_URL')
    api_key = os.environ.get('POSTIZ_API_KEY')
    if not url or not api_key:
        raise RuntimeError('POSTIZ_API_URL and POSTIZ_API_KEY must be set to publish')

    files = {'file': open(video_path, 'rb')}
    data = {
        'title': title,
        'description': description,
        'tags': ','.join(tags)
    }
    headers = {'Authorization': f'Bearer {api_key}'}
    r = requests.post(url, headers=headers, data=data, files=files)
    r.raise_for_status()
    return r.json()


if __name__ == '__main__':
    print('Publisher module: set POSTIZ_API_URL and POSTIZ_API_KEY to enable publish')
