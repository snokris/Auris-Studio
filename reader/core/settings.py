"""
Persistent settings — stored in data/settings.json.
All path defaults are resolved relative to the repo root at runtime,
so the app works on Windows, Linux, and macOS without modification.
"""

import json
import sys
from pathlib import Path

# reader/ directory
_APP_DIR   = Path(__file__).resolve().parent.parent
# E:\Ebook-Reader\ (or equivalent on other platforms)
_REPO_ROOT = _APP_DIR.parent

SETTINGS_FILE = _APP_DIR / 'data' / 'settings.json'

_DEFAULT_HIGGS_MODEL_PATH = str(_REPO_ROOT / 'model_backup' / 'Higgs-TTS-3-4B')
_DEFAULT_HIGGS_MLX_MODEL_PATH = str(
    _REPO_ROOT / 'model_backup' / 'Higgs-TTS-3-4B-MLX'
)
LEGACY_NARRATOR_INSTRUCT = 'female, middle-aged, moderate pitch, american accent'
DEFAULT_NARRATOR_INSTRUCT = 'male, elderly, low pitch, british accent'
TTS_EXPRESSION_POLICY_VERSION = 2

DEFAULTS: dict = {
    # Higgs TTS 3. Auto selects native MLX on Apple Silicon and the existing
    # Transformers worker elsewhere.
    'higgs_backend': 'auto',            # 'auto' | 'mlx' | 'transformers'
    'higgs_model_source': 'download',  # 'local' | 'download' (HF cache)
    'higgs_model_path': _DEFAULT_HIGGS_MODEL_PATH,
    'higgs_model_repo': 'multimodalart/higgs-audio-v3-tts-4b-transformers',
    'higgs_mlx_model_source': 'download',  # 'local' | 'download'
    'higgs_mlx_model_path': _DEFAULT_HIGGS_MLX_MODEL_PATH,
    'higgs_mlx_model_repo': 'bosonai/higgs-tts-3-4b',
    'higgs_mlx_batch_size': 5,
    'higgs_mlx_hybrid_questions': True,
    'higgs_temperature': 0.8,
    'higgs_top_p': 0.95,
    'higgs_top_k': 50,
    'higgs_max_new_tokens': 1024,
    'higgs_seed': 123,
    # raw = match the reference Gradio app (plain text, no automatic controls)
    # expressive = apply Auris Studio normalization, scene speed and expression tags
    'higgs_prompt_mode': 'raw',
    'higgs_default_emotion': 'none',
    'higgs_default_style': 'none',
    'higgs_default_expressive': 'none',

    # Narrator
    'narrator_instruct': DEFAULT_NARRATOR_INSTRUCT,
    'single_narrator_mode': False,

    # Character and dialogue-speaker detection. "llm" uses any local
    # OpenAI-compatible server (LM Studio, Ollama, llama.cpp); "legacy" keeps
    # the original English spaCy/regex detector.
    'character_detection_mode': 'legacy',
    'llm_base_url': 'http://127.0.0.1:1234/v1',
    'llm_api_key': '',
    'llm_model': '',
    'llm_timeout_sec': 600,
    'llm_max_output_tokens': 8192,
    'llm_max_characters': 60,
    # Keep both prompt and compact per-dialogue JSON comfortably inside the
    # output budget. A normal novel is therefore analyzed one chapter/request.
    'llm_batch_chars': 10000,

    # Playback defaults
    'default_speed': 1.0,

    # TTS text processing
    # Expand numbers/dates/currency into spoken form before synthesis.
    # EN/ZH prefer WeTextProcessing (optional); other languages use num2words.
    'normalize_text': True,

    # Internal migration marker for legacy expression-tag handling.
    'tts_expression_policy_version': TTS_EXPRESSION_POLICY_VERSION,

    # Export defaults
    'audio_format': 'wav',
    'subtitle_format': 'ass',

    # MP3 encoding. The TTS output is 24 kHz mono speech, so MPEG-2 Layer III
    # applies and anything above 160 kbps is clamped by the encoder anyway.
    # VBR is the default: the silence between segments costs almost nothing,
    # while CBR pays full price for it.
    'mp3_mode': 'vbr',                 # 'vbr' | 'cbr'
    'mp3_vbr_quality': 7,              # libmp3lame -q:a, 0 = best … 9 = smallest
    'mp3_bitrate': 48,                 # kbps, used when mp3_mode == 'cbr'

    # Spoken-program pauses (seconds). Used by both export and playback.
    'export_pause_segment': 0.35,      # between ordinary sentences
    'export_pause_dialogue': 0.55,     # between two consecutive dialogue turns
    'export_pause_ellipsis': 1.5,      # after a trailing "..." / "…"
    'export_pause_paragraph': 0.85,    # at a real paragraph boundary
    'export_pause_chapter': 2.0,       # between two chapters in a joined file

    # Optional studio polish on exported chapters: gentle EQ + compression and
    # two-pass EBU R128 loudness matching via ffmpeg. Off by default so the
    # raw engine output stays comparable by ear.
    'audio_mastering': False,

    # Joined output. When on, the export writes no per-chapter files at all:
    # once every chapter's audio exists it is concatenated into 1-4 files,
    # each encoded once, with subtitles retimed to match.
    'export_join_parts': False,
    'export_part_count': 1,            # 1-4

    # UI
    'theme': 'light',
    'font_size': 18,
    'font_family': 'serif',
    'line_height': 1.9,
}


_LEGACY_THEMES = {'night': 'dark', 'amoled': 'dark', 'sepia': 'light', 'paper': 'light'}


def load() -> dict:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, encoding='utf-8') as f:
                saved = json.load(f)
            # Keep only settings supported by the current Higgs-only build.
            # This also removes obsolete engine keys from older settings files.
            saved = {key: value for key, value in saved.items() if key in DEFAULTS}
            merged = {**DEFAULTS, **saved}
            narrator_instruct = str(merged.get('narrator_instruct') or '').strip().lower()
            if narrator_instruct in {'', LEGACY_NARRATOR_INSTRUCT.lower()}:
                merged['narrator_instruct'] = DEFAULT_NARRATOR_INSTRUCT
            theme = str(merged.get('theme') or 'light').strip().lower()
            theme = _LEGACY_THEMES.get(theme, theme)
            merged['theme'] = theme if theme in ('light', 'dark') else 'light'
            return merged
        except Exception:
            pass
    return dict(DEFAULTS)


def save(updates: dict) -> dict:
    current = load()
    current.update({key: value for key, value in updates.items() if key in DEFAULTS})
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(current, f, indent=2)
    return current


def migrate_tts_expression_policy_version() -> bool:
    """Record the expression policy and report whether segment prompts are stale."""
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, encoding='utf-8') as f:
                saved = json.load(f)
        else:
            saved = {}
        previous = int(saved.get('tts_expression_policy_version', 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        previous = 0

    if previous == TTS_EXPRESSION_POLICY_VERSION:
        return False

    save({'tts_expression_policy_version': TTS_EXPRESSION_POLICY_VERSION})
    return True


def get(key: str, default=None):
    return load().get(key, default)


# ── spaCy status ──────────────────────────────────────────────────────────────

def spacy_status() -> dict:
    """Returns {'installed': bool, 'model_installed': bool, 'model': str}"""
    try:
        import spacy
        spacy_ok = True
    except ImportError:
        return {'installed': False, 'model_installed': False, 'model': 'en_core_web_sm'}

    try:
        spacy.load('en_core_web_sm')
        model_ok = True
    except OSError:
        model_ok = False

    return {'installed': spacy_ok, 'model_installed': model_ok, 'model': 'en_core_web_sm'}


def install_spacy_model() -> dict:
    """Run 'python -m spacy download en_core_web_sm' as a subprocess."""
    import subprocess
    python = sys.executable
    result = subprocess.run(
        [python, '-m', 'spacy', 'download', 'en_core_web_sm'],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return {'ok': True, 'message': 'en_core_web_sm installed successfully.'}
    return {'ok': False, 'message': result.stderr or result.stdout}
