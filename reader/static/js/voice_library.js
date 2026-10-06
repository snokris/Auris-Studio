const voiceLibraryStatus = document.getElementById('voice-library-status');
const voiceLibraryAudio = new Audio();
let syntheticCandidateId = null;
let activeVoicePreviewButton = null;
let voiceMessageTimer = null;
const VOICE_TAG_CHOICES = {
  gender: ['unknown', 'female', 'male'],
  age: ['unknown', 'child', 'teenager', 'young adult', 'middle-aged', 'elderly'],
  pitch: ['unknown', 'very low pitch', 'low pitch', 'moderate pitch', 'high pitch', 'very high pitch'],
  accent: ['unknown', 'hungarian', 'other'],
};

function newVoiceTags(kind) {
  return Object.fromEntries(Object.keys(VOICE_TAG_CHOICES).map(key => [
    key, document.getElementById(`${kind}-voice-${key}`).value,
  ]));
}

function resetVoiceTags(kind) {
  for (const key of Object.keys(VOICE_TAG_CHOICES)) {
    document.getElementById(`${kind}-voice-${key}`).value = 'unknown';
  }
}

function applyVoiceFilters() {
  const filters = Object.fromEntries(Object.keys(VOICE_TAG_CHOICES).map(key => [
    key, document.getElementById(`voice-filter-${key}`).value,
  ]));
  document.querySelectorAll('.voice-library-card').forEach(card => {
    card.classList.toggle('hidden', Object.entries(filters).some(
      ([key, value]) => value && card.dataset[key] !== value
    ));
  });
}

function clearVoiceFilters() {
  for (const key of Object.keys(VOICE_TAG_CHOICES)) {
    document.getElementById(`voice-filter-${key}`).value = '';
  }
}

for (const key of Object.keys(VOICE_TAG_CHOICES)) {
  document.getElementById(`voice-filter-${key}`).addEventListener('change', applyVoiceFilters);
}

function voiceMessage(message, error = false) {
  voiceLibraryStatus.textContent = message;
  voiceLibraryStatus.className = `status-hint ${error ? 'status-error' : 'status-ok'}`;
  clearTimeout(voiceMessageTimer);
  voiceMessageTimer = setTimeout(() => { voiceLibraryStatus.textContent = ''; }, 8000);
}

async function voiceResponse(response) {
  const result = await response.json();
  if (!response.ok || result.error) throw new Error(result.error || `HTTP ${response.status}`);
  return result;
}

async function waitForVoiceModel() {
  for (let attempt = 0; attempt < 90; attempt++) {
    const status = await voiceResponse(await fetch('/api/tts/status'));
    if (status.state === 'ready') return;
    if (status.state === 'error') throw new Error(status.error || 'Higgs failed to load.');
    voiceMessage('Loading Higgs…');
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  throw new Error('Higgs did not become ready in time.');
}

function setVoicePreviewState(button, state) {
  button.disabled = state === 'loading';
  button.classList.toggle('is-loading', state === 'loading');
  button.classList.toggle('is-playing', state === 'playing');
  button.setAttribute('aria-busy', String(state === 'loading'));
  button.setAttribute('aria-pressed', String(state === 'playing'));
  button.querySelector('.preview-label').textContent =
    state === 'loading' ? 'Generating…' : state === 'playing' ? '■ Stop' : '▶ Preview';
}

function stopVoicePreview() {
  voiceLibraryAudio.pause();
  voiceLibraryAudio.currentTime = 0;
  if (activeVoicePreviewButton) setVoicePreviewState(activeVoicePreviewButton, 'idle');
  activeVoicePreviewButton = null;
}

async function playVoiceUrl(url, button) {
  stopVoicePreview();
  activeVoicePreviewButton = button;
  voiceLibraryAudio.src = url;
  try {
    await voiceLibraryAudio.play();
    setVoicePreviewState(button, voiceLibraryAudio.paused || voiceLibraryAudio.ended ? 'idle' : 'playing');
  } catch (error) {
    setVoicePreviewState(button, 'idle');
    activeVoicePreviewButton = null;
    throw error;
  }
}

voiceLibraryAudio.addEventListener('ended', stopVoicePreview);

function voicePreviewButton() {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'btn btn-sm btn-ghost preview-btn';
  button.setAttribute('aria-busy', 'false');
  button.setAttribute('aria-pressed', 'false');
  const spinner = document.createElement('span');
  spinner.className = 'preview-spinner';
  spinner.setAttribute('aria-hidden', 'true');
  const label = document.createElement('span');
  label.className = 'preview-label';
  label.textContent = '▶ Preview';
  button.append(spinner, label);
  return button;
}

function voiceButton(label, action) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'btn btn-sm btn-ghost';
  button.textContent = label;
  button.addEventListener('click', action);
  return button;
}

async function loadVoiceLibrary() {
  try {
    stopVoicePreview();
    const voices = await voiceResponse(await fetch('/api/voices'));
    for (const kind of ['synthetic', 'reference']) {
      const container = document.getElementById(`${kind}-voice-list`);
      container.replaceChildren();
      const group = voices.filter(voice => voice.kind === kind);
      if (!group.length) {
        const empty = document.createElement('p');
        empty.className = 'studio-note';
        empty.textContent = `No saved ${kind} voices yet.`;
        container.appendChild(empty);
      }
      for (const voice of group) container.appendChild(renderVoice(voice));
    }
    applyVoiceFilters();
  } catch (error) {
    voiceMessage(`Could not load voices: ${error.message}`, true);
  }
}

function renderVoice(voice) {
  const card = document.createElement('details');
  card.className = 'voice-library-card';
  for (const key of Object.keys(VOICE_TAG_CHOICES)) card.dataset[key] = voice[key] || 'unknown';
  const summary = document.createElement('summary');
  summary.textContent = voice.name;
  if (voice.usage_count) {
    const used = document.createElement('span');
    used.className = 'muted';
    used.textContent = ` · ${voice.usage_count} book(s)`;
    summary.appendChild(used);
  }
  const editor = document.createElement('div');
  editor.className = 'voice-library-editor';
  const nameLabel = document.createElement('label');
  nameLabel.textContent = 'Voice name';
  const name = document.createElement('input');
  name.className = 'text-input';
  name.value = voice.name;
  name.maxLength = 80;
  name.setAttribute('aria-label', `${voice.name} name`);
  nameLabel.appendChild(name);
  const transcriptLabel = document.createElement('label');
  transcriptLabel.textContent = 'Exact words in this voice’s WAV';
  const transcript = document.createElement('textarea');
  transcript.className = 'text-input';
  transcript.rows = 2;
  transcript.maxLength = 20000;
  transcript.value = voice.ref_text || '';
  transcript.setAttribute('aria-label', `${voice.name} reference transcript`);
  if (voice.kind === 'synthetic') {
    transcript.readOnly = true;
    transcript.title = 'This is the exact text spoken in the saved sample. Replace the candidate to change it.';
  }
  transcriptLabel.appendChild(transcript);
  const previewTextSection = document.createElement('div');
  previewTextSection.className = 'preview-text-section';
  const previewTextLabel = document.createElement('label');
  previewTextLabel.textContent = 'Text to read in preview';
  const previewText = document.createElement('textarea');
  previewText.className = 'reference-text';
  previewText.rows = 3;
  previewText.maxLength = 1000;
  previewText.value = window.DEFAULT_SYNTHETIC_SAMPLE_TEXT;
  previewTextLabel.appendChild(previewText);
  const resetPreviewText = voiceButton('Reset to default', () => {
    previewText.value = window.DEFAULT_SYNTHETIC_SAMPLE_TEXT;
    if (activeVoicePreviewButton === previewButton) stopVoicePreview();
  });
  previewTextSection.append(previewTextLabel, resetPreviewText);
  const tags = document.createElement('div');
  tags.className = 'voice-tag-grid';
  const tagInputs = {};
  for (const [key, options] of Object.entries(VOICE_TAG_CHOICES)) {
    const label = document.createElement('label');
    label.textContent = key[0].toUpperCase() + key.slice(1);
    const select = document.createElement('select');
    select.className = 'select-input';
    select.setAttribute('aria-label', `${voice.name} ${key}`);
    for (const option of options) {
      select.add(new Option(option === 'unknown' ? 'Unspecified' : option, option));
    }
    select.value = voice[key] || 'unknown';
    tagInputs[key] = select;
    label.appendChild(select);
    tags.appendChild(label);
  }
  const actions = document.createElement('div');
  actions.className = 'reference-actions';
  const previewButton = voicePreviewButton();
  previewButton.addEventListener('click', async () => {
    if (activeVoicePreviewButton === previewButton) {
      stopVoicePreview();
      return;
    }
    stopVoicePreview();
    try {
      setVoicePreviewState(previewButton, 'loading');
      await waitForVoiceModel();
      voiceMessage(`Generating preview: ${voice.name}…`);
      const result = await voiceResponse(await fetch(`/api/voices/${voice.id}/preview`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text: getPreviewText(previewText)}),
      }));
      await playVoiceUrl(result.audio_url, previewButton);
      voiceMessage(`Playing: ${voice.name}`);
    } catch (error) {
      setVoicePreviewState(previewButton, 'idle');
      voiceMessage(error.message, true);
    }
  });
  previewText.addEventListener('input', () => {
    if (activeVoicePreviewButton === previewButton) stopVoicePreview();
  });
  actions.appendChild(previewButton);
  actions.appendChild(voiceButton('Save edits', async () => {
    try {
      const result = await voiceResponse(await fetch(`/api/voices/${voice.id}`, {
        method: 'PATCH', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          name: name.value.trim(), ref_text: transcript.value.trim(),
          ...Object.fromEntries(Object.entries(tagInputs).map(([key, input]) => [key, input.value])),
        }),
      }));
      voiceMessage(`Updated ${name.value.trim()}. ${result.affected_books} book(s) use this voice.`);
      await loadVoiceLibrary();
    } catch (error) { voiceMessage(error.message, true); }
  }));
  actions.appendChild(voiceButton('Export', () => {
    window.location.href = `/api/voices/${voice.id}/export`;
  }));
  if (voice.kind === 'reference') {
    const replacement = document.createElement('input');
    replacement.type = 'file';
    replacement.accept = '.wav,audio/wav';
    replacement.setAttribute('aria-label', `Replace WAV for ${voice.name}`);
    replacement.addEventListener('change', async () => {
      const file = replacement.files?.[0];
      if (!file) return;
      const form = new FormData();
      form.append('file', file);
      form.append('ref_text', transcript.value.trim());
      try {
        await voiceResponse(await fetch(`/api/voices/${voice.id}/audio`, {method: 'PUT', body: form}));
        voiceMessage(`Replaced reference WAV for ${voice.name}.`);
        await loadVoiceLibrary();
      } catch (error) { voiceMessage(error.message, true); }
    });
    actions.appendChild(replacement);
  } else {
    actions.appendChild(voiceButton('Replace with current candidate', async () => {
      if (!syntheticCandidateId) { voiceMessage('Generate a candidate first.', true); return; }
      if (!confirm(`Replace the sound of “${voice.name}” for every book using it?`)) return;
      try {
        await voiceResponse(await fetch(`/api/voices/${voice.id}/candidate`, {
          method: 'PUT', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({candidate_id: syntheticCandidateId}),
        }));
        voiceMessage(`Replaced the sound of ${voice.name}.`);
        await loadVoiceLibrary();
      } catch (error) { voiceMessage(error.message, true); }
    }));
  }
  actions.appendChild(voiceButton('Delete', async () => {
    if (!confirm(`Delete “${voice.name}”? ${voice.usage_count || 0} book(s) using it will need another voice.`)) return;
    try {
      const result = await voiceResponse(await fetch(`/api/voices/${voice.id}`, {method: 'DELETE'}));
      voiceMessage(`Deleted ${voice.name}. ${result.affected_books} book(s) need a new voice.`);
      await loadVoiceLibrary();
    } catch (error) { voiceMessage(error.message, true); }
  }));
  editor.append(nameLabel, transcriptLabel, tags, previewTextSection, actions);
  card.append(summary, editor);
  return card;
}

const voicePreviewText = document.getElementById('synthetic-sample-text');
const referencePreviewText = document.getElementById('reference-sample-text');
const candidatePreviewButton = document.getElementById('generate-synthetic-voice');
const newCandidateButton = document.getElementById('new-synthetic-candidate');
const referencePreviewButton = document.getElementById('preview-reference-voice');

function getPreviewText(field) {
  const text = field.value.trim() || window.DEFAULT_SYNTHETIC_SAMPLE_TEXT;
  field.value = text;
  return text;
}

function getVoicePreviewText() { return getPreviewText(voicePreviewText); }
function getReferencePreviewText() { return getPreviewText(referencePreviewText); }

function clearSyntheticCandidate() {
  syntheticCandidateId = null;
  document.getElementById('save-synthetic-voice').disabled = true;
  newCandidateButton.disabled = true;
  if (activeVoicePreviewButton === candidatePreviewButton) stopVoicePreview();
}

voicePreviewText.addEventListener('input', clearSyntheticCandidate);
voicePreviewText.addEventListener('blur', getVoicePreviewText);
referencePreviewText.addEventListener('blur', getReferencePreviewText);
referencePreviewText.addEventListener('input', () => {
  if (activeVoicePreviewButton === referencePreviewButton) stopVoicePreview();
});
document.getElementById('reference-voice-text').addEventListener('input', () => {
  if (activeVoicePreviewButton === referencePreviewButton) stopVoicePreview();
});
document.getElementById('reference-voice-file').addEventListener('change', () => {
  if (activeVoicePreviewButton === referencePreviewButton) stopVoicePreview();
});
document.getElementById('reset-voice-preview-text').addEventListener('click', () => {
  voicePreviewText.value = window.DEFAULT_SYNTHETIC_SAMPLE_TEXT;
  clearSyntheticCandidate();
});
document.getElementById('reset-reference-preview-text').addEventListener('click', () => {
  referencePreviewText.value = window.DEFAULT_SYNTHETIC_SAMPLE_TEXT;
  if (activeVoicePreviewButton === referencePreviewButton) stopVoicePreview();
});

referencePreviewButton.addEventListener('click', async () => {
  if (activeVoicePreviewButton === referencePreviewButton) {
    stopVoicePreview();
    return;
  }
  const file = document.getElementById('reference-voice-file').files?.[0];
  const transcript = document.getElementById('reference-voice-text').value.trim();
  if (!file || !transcript) {
    voiceMessage('Choose a reference WAV and enter the exact words spoken in it.', true);
    return;
  }
  stopVoicePreview();
  setVoicePreviewState(referencePreviewButton, 'loading');
  try {
    await waitForVoiceModel();
    voiceMessage('Generating reference voice preview…');
    const form = new FormData();
    form.append('file', file);
    form.append('ref_text', transcript);
    form.append('preview_text', getReferencePreviewText());
    const result = await voiceResponse(await fetch('/api/voices/reference/preview', {
      method: 'POST', body: form,
    }));
    await playVoiceUrl(result.audio_url, referencePreviewButton);
    voiceMessage('Playing the text from the reference preview field.');
  } catch (error) {
    setVoicePreviewState(referencePreviewButton, 'idle');
    voiceMessage(error.message, true);
  }
});

async function previewSyntheticCandidate(forceNew = false) {
  if (activeVoicePreviewButton === candidatePreviewButton && !forceNew) {
    stopVoicePreview();
    return;
  }
  stopVoicePreview();
  setVoicePreviewState(candidatePreviewButton, 'loading');
  newCandidateButton.disabled = true;
  try {
    await waitForVoiceModel();
    if (!syntheticCandidateId || forceNew) {
      clearSyntheticCandidate();
      voiceMessage('Generating a synthetic voice…');
      const requestedText = getVoicePreviewText();
      const result = await voiceResponse(await fetch('/api/voices/synthetic/candidates', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text: requestedText}),
      }));
      if (voicePreviewText.value.trim() !== requestedText) {
        voiceMessage('Preview text changed. Preview again to create a matching voice.');
        return;
      }
      syntheticCandidateId = result.candidate_id;
      document.getElementById('save-synthetic-voice').disabled = false;
    }
    await playVoiceUrl(`/api/audio/${syntheticCandidateId}`, candidatePreviewButton);
    voiceMessage('Candidate ready. Name and save it, or try another variation.');
  } catch (error) {
    setVoicePreviewState(candidatePreviewButton, 'idle');
    voiceMessage(error.message, true);
  } finally {
    if (!syntheticCandidateId) setVoicePreviewState(candidatePreviewButton, 'idle');
    newCandidateButton.disabled = !syntheticCandidateId;
  }
}

candidatePreviewButton.addEventListener('click', () => previewSyntheticCandidate());
newCandidateButton.addEventListener('click', () => previewSyntheticCandidate(true));

document.getElementById('save-synthetic-voice').addEventListener('click', async () => {
  if (!syntheticCandidateId) return;
  try {
    const result = await voiceResponse(await fetch('/api/voices/synthetic', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        name: document.getElementById('synthetic-voice-name').value.trim(),
        candidate_id: syntheticCandidateId,
        ...newVoiceTags('synthetic'),
      }),
    }));
    voiceMessage(`Saved synthetic voice: ${result.name}.`);
    document.getElementById('synthetic-voice-name').value = '';
    resetVoiceTags('synthetic');
    clearVoiceFilters();
    await loadVoiceLibrary();
  } catch (error) { voiceMessage(error.message, true); }
});

document.getElementById('save-reference-voice').addEventListener('click', async () => {
  const file = document.getElementById('reference-voice-file').files?.[0];
  const form = new FormData();
  form.append('name', document.getElementById('reference-voice-name').value.trim());
  form.append('ref_text', document.getElementById('reference-voice-text').value.trim());
  for (const [key, value] of Object.entries(newVoiceTags('reference'))) form.append(key, value);
  if (file) form.append('file', file);
  try {
    const result = await voiceResponse(await fetch('/api/voices/reference', {
      method: 'POST', body: form,
    }));
    voiceMessage(`Saved reference voice: ${result.name}.`);
    document.getElementById('reference-voice-name').value = '';
    document.getElementById('reference-voice-text').value = '';
    document.getElementById('reference-voice-file').value = '';
    resetVoiceTags('reference');
    clearVoiceFilters();
    await loadVoiceLibrary();
  } catch (error) { voiceMessage(error.message, true); }
});

document.getElementById('voice-import-button').addEventListener('click', async () => {
  const input = document.getElementById('voice-import-file');
  const file = input.files?.[0];
  if (!file) { voiceMessage('Choose an .aurisvoice file first.', true); return; }
  const form = new FormData();
  form.append('file', file);
  form.append('kind', document.getElementById('voice-import-kind').value);
  try {
    const result = await voiceResponse(await fetch('/api/voices/import', {
      method: 'POST', body: form,
    }));
    voiceMessage(`Imported voice: ${result.name}.`);
    input.value = '';
    clearVoiceFilters();
    await loadVoiceLibrary();
  } catch (error) { voiceMessage(error.message, true); }
});

loadVoiceLibrary();
