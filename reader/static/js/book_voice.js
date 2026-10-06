const bookVoiceSelect = document.getElementById('book-narrator-voice');
const bookVoiceStatus = document.getElementById('book-voice-status');
const bookPreviewButton = document.getElementById('book-voice-preview');
const bookPreviewAudio = document.getElementById('preview-audio');
const bookPreviewText = document.getElementById('narrator-preview-text');
let bookPreviewState = 'idle';

function getBookPreviewText() {
  const text = bookPreviewText.value.trim() || window.DEFAULT_NARRATOR_PREVIEW_TEXT;
  bookPreviewText.value = text;
  return text;
}

document.getElementById('reset-narrator-preview-text').addEventListener('click', () => {
  bookPreviewText.value = window.DEFAULT_NARRATOR_PREVIEW_TEXT;
});
bookPreviewText.addEventListener('blur', getBookPreviewText);

function setBookVoiceStatus(message) {
  bookVoiceStatus.textContent = message;
}

function setBookPreviewState(state) {
  bookPreviewState = state;
  bookPreviewButton.disabled = state === 'loading';
  bookPreviewButton.classList.toggle('is-loading', state === 'loading');
  bookPreviewButton.classList.toggle('is-playing', state === 'playing');
  bookPreviewButton.setAttribute('aria-busy', String(state === 'loading'));
  bookPreviewButton.setAttribute('aria-pressed', String(state === 'playing'));
  bookPreviewButton.querySelector('.preview-label').textContent =
    state === 'loading' ? 'Generating…' : state === 'playing' ? '■ Stop' : '▶ Preview';
}

async function loadBookVoices() {
  try {
    const response = await fetch('/api/voices');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const voices = await response.json();
    bookVoiceSelect.replaceChildren();
    const placeholder = new Option('Choose a saved voice…', '');
    bookVoiceSelect.add(placeholder);
    for (const kind of ['synthetic', 'reference']) {
      const group = document.createElement('optgroup');
      group.label = kind === 'synthetic' ? 'Synthetic voices' : 'Reference voices';
      for (const voice of voices.filter(item => item.kind === kind)) {
        group.appendChild(new Option(voice.name, String(voice.id)));
      }
      if (group.children.length) bookVoiceSelect.add(group);
    }
    bookVoiceSelect.value = String(window.BOOK_VOICE_ID || '');
    if (window.BOOK_VOICE_ID && !bookVoiceSelect.value) {
      setBookVoiceStatus('The previously selected voice is missing. Choose another voice.');
    } else if (!voices.length) {
      setBookVoiceStatus('No saved voices yet. Create one in Settings first.');
    }
    bookPreviewButton.disabled = !bookVoiceSelect.value;
    document.getElementById('book-voice-save').disabled = !bookVoiceSelect.value;
  } catch (error) {
    setBookVoiceStatus(`Could not load voices: ${error.message}`);
  }
}

bookVoiceSelect.addEventListener('change', () => {
  bookPreviewAudio.pause();
  bookPreviewAudio.currentTime = 0;
  setBookPreviewState('idle');
  bookPreviewButton.disabled = !bookVoiceSelect.value;
  document.getElementById('book-voice-save').disabled = !bookVoiceSelect.value;
  setBookVoiceStatus(bookVoiceSelect.value ? 'Preview the voice, then save it for this book.' : 'Choose a saved voice.');
});

document.getElementById('book-voice-save').addEventListener('click', async () => {
  const voiceId = Number(bookVoiceSelect.value);
  if (!voiceId) return;
  const response = await fetch(`/api/books/${window.BOOK_ID}/narrator-voice`, {
    method: 'PUT', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({voice_id: voiceId, preview_text: getBookPreviewText()}),
  });
  const result = await response.json();
  if (!response.ok) {
    setBookVoiceStatus(result.error || 'Could not save the voice.');
    return;
  }
  window.BOOK_VOICE_ID = voiceId;
  setBookVoiceStatus(`Saved: ${result.name}. Preview text is saved for this book.`);
});

bookPreviewButton.addEventListener('click', async () => {
  if (bookPreviewState === 'playing') {
    bookPreviewAudio.pause();
    bookPreviewAudio.currentTime = 0;
    setBookPreviewState('idle');
    return;
  }
  if (bookPreviewState === 'loading' || !bookVoiceSelect.value) return;
  setBookPreviewState('loading');
  try {
    const response = await fetch(`/api/books/${window.BOOK_ID}/narrator-voice/preview`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({voice_id: Number(bookVoiceSelect.value), preview_text: getBookPreviewText()}),
    });
    const result = await response.json();
    if (!response.ok || !result.audio_url) throw new Error(result.error || 'Preview failed.');
    bookPreviewAudio.src = result.audio_url;
    await bookPreviewAudio.play();
    setBookPreviewState(bookPreviewAudio.paused || bookPreviewAudio.ended ? 'idle' : 'playing');
  } catch (error) {
    setBookVoiceStatus(error.message || String(error));
  } finally {
    if (bookPreviewState === 'loading') setBookPreviewState('idle');
  }
});

for (const eventName of ['ended', 'pause', 'error']) {
  bookPreviewAudio.addEventListener(eventName, () => {
    if (bookPreviewState === 'playing') setBookPreviewState('idle');
  });
}

loadBookVoices();
