# yt-brainrot

Lokalny, bezkosztowy pipeline do automatycznego tworzenia i publikowania krótkich "brainrot" story na YouTube Shorts.

Cel: generować tekst (Ollama), TTS (Coqui/Piper/pyttsx3), tło (PIL / opcjonalnie Stable Diffusion), montować shorty (FFmpeg) i publikować przez Postiz (szkic).

Uwaga: projekt daje modularne backendy — musisz zainstalować/ustawić lokalne modele (Ollama, TTS czy SD) jeśli chcesz lepszej jakości. System działa też w trybie minimalnym (offline, free) używając prostych fallbacków.

Szybki start

1. Zainstaluj wymagania (najprostsze):

```bash
python -m pip install -r requirements.txt
```

2. Upewnij się, że `ffmpeg` jest w PATH.

3. (opcjonalnie) Zainstaluj i skonfiguruj `ollama` i model `bielik-4b-v3.0` dla lepszych wyników LLM.

4. Uruchom przykładowy pipeline (generuje jeden short):

```bash
python scripts/pipeline.py --count 1
```

Struktura projektu

- `scripts/pipeline.py` — orkiestrowanie kroków
- `yt_brainrot/llm.py` — interakcja z Ollama (lub fallback)
- `yt_brainrot/tts.py` — lokalne TTS (Coqui / piper / pyttsx3 fallback)
- `yt_brainrot/visual.py` — generowanie obrazu tła (PIL fallback)
- `yt_brainrot/editor.py` — łączenie audio + obrazu w short (FFmpeg)
- `yt_brainrot/publisher.py` — szkic publikatora przez Postiz (wymaga konfiguracji; set `POSTIZ_API_URL` and `POSTIZ_API_KEY` to enable publishing)

Publikacja przez Postiz

`yt_brainrot/publisher.py` zawiera szkielet publikowania — wymaga ustawienia `POSTIZ_API_URL` i `POSTIZ_API_KEY` w zmiennych środowiskowych. API Postiz może wymagać dodatkowych parametrów; należy uzupełnić zgodnie z dokumentacją Postiz.

Tryby pracy

- minimal: działa offline, używa placeholderów (PIL obraz, pyttsx3 TTS)
- full: używa lokalnego Ollama i Coqui/Piper oraz Stable Diffusion (jeśli zainstalowane)

Jeśli chcesz, mogę dodać integrację z Stable Diffusion z optymalizacją VRAM dla RTX4050, lub skonfigurować Coqui TTS z polskim modelem.

Automatic1111 (A1111) — integracja i wskazówki dla RTX4050 (6GB VRAM)

- Moduł integracyjny: `yt_brainrot/sd_a1111.py` wysyła żądania do lokalnego WebUI A1111 przez `http://127.0.0.1:7860/sdapi/v1/txt2img`.
- Typowe wywołanie (przykład):

```python
from yt_brainrot.sd_a1111 import generate_image_a1111
generate_image_a1111('surreal meme style, absurd brainrot aesthetic, low detail, vertical 9:16', 'outputs/images/a1111_bg.jpg')
```

Rekomendacje uruchomienia Automatic1111 dla niskiego VRAM (RTX4050 6GB):

- Uruchamiaj WebUI z flagami redukującymi pamięć:

```bash
python launch.py --medvram --no-half --xformers
```

- Ustawienia obrazu:
	- generuj niższą rozdzielczość (np. 720x1280) i podnieś rozdzielczość do 1080x1920 przez upscaler/FFmpeg, lub użyj opcji `hires_fix` w A1111 (upscale potem crop).
	- zmniejsz liczbę `steps` (np. 20) i użyj lżejszego samplera.

- Jeśli masz zainstalowane rozszerzenia jak `Stable Diffusion Upscaler` lub `ESRGAN`, możesz generować mniejsze obrazy i upscalować je bez przekraczania VRAM.

Ograniczenia:
- Dla pionowych 1080x1920 przy pełnej jakości SDXL/SD1.5 może brakować VRAM na RTX4050; rekomendowany workflow: 1) generuj 720x1280, 2) upscaluj do 1080x1920.

# yt-brainrot
brainrot

Uruchomienie webowego dashboardu

1. Zainstaluj wymagania:

```bash
python -m pip install -r requirements.txt
```

2. Uruchom serwer deweloperski (Flask):

```bash
python webapp/app.py
```

3. Produkcyjnie użyj `gunicorn`:

```bash
gunicorn -w 1 -b 0.0.0.0:5000 webapp.app:app
```

Panel webowy: otwórz `http://localhost:5000`, ustaw liczbę shortów i kliknij "Generuj". Wyniki zostaną zapisane w katalogu `outputs/web_<timestamp>`.

Konfiguracja i UI

- Ustawienia endpointów: otwórz `Konfiguracja modułów` (Config) w UI i wpisz adresy lokalnych serwisów: `Ollama URL`, `Piper/Coqui URL`, `A1111 (SD) URL`. Zapisane wartości trzymają się w `localStorage` i są stosowane przy wywołaniu pipeline.
- TTS: w głównym panelu masz przełącznik `Włącz TTS`, dropdown wyboru `Głos` (pobierany z serwera TTS, jeśli dostępny) oraz `Tempo`. Włącz/wyłącz TTS aby wygenerować tylko tekst (story) lub pełne shorty z audio.
- Endpoint `/functions/v1/run-pipeline` obsługuje dodatkowe pola JSON: `voice`, `speed`, `piperUrl`, `ollamaUrl`, `sdUrl`, `generateTTS`.

Tryby pracy i uruchamianie

- Tryb minimalny (out-of-the-box): działa offline, używa PIL jako generatora obrazu i espeak/pyttsx3 jako TTS.
- Tryb pełny: skonfiguruj lokalne serwisy i wpisz ich URL-e w panelu konfiguracyjnym — system użyje ich jeśli są dostępne.

Przykładowe wywołanie endpointu `run-pipeline` (curl):

```bash
curl -X POST -H "Content-Type: application/json" \
	-d '{"storyPrompt":"Krótka testowa","generateTTS":false}' \
	http://localhost:5000/functions/v1/run-pipeline
```

Frontend (opcjonalnie lokalny dev):

1. Przejdź do `frontend_template` i zainstaluj zależności:

```bash
cd frontend_template
npm install
```

2. Ustaw zmienną środowiskową `VITE_SUPABASE_URL` na `http://localhost:5000` (Flask), np. w `.env`:

```
VITE_SUPABASE_URL=http://localhost:5000
```

3. Uruchom dev server frontendu:

```bash
npm run dev
```

To pozwoli UI komunikować się z lokalnym Flask-em implementującym Supabase-style functions (`/functions/v1/*`).

Web UI: w sekcji Konfiguracja możesz teraz ustawić lokalne endpointy (`Ollama URL`, `A1111 URL`, `Piper/Coqui URL`) oraz domyślny głos i tempo TTS. W głównym panelu dostępny jest toggle TTS, dropdown wyboru głosu oraz pole do regulacji tempa.
