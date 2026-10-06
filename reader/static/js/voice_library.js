const voiceLibraryStatus = document.getElementById('voice-library-status');
const voiceLibraryAudio = new Audio();
let syntheticCandidateId = null;
const VOICE_TAG_CHOICES = {
  gender: ['unknown', 'female', 'male'],
  age: ['unknown', 'child', 'teenager', 'young adult', 'middle-aged', 'elderly'],
  pitch: ['unknown', 'very low pitch', 'low pitch', 'moderate pitch', 'high pitch', 'very high pitch'],
  accent: ['unknown', 'hungarian', 'other'],
};

function newVoiceTags() {
  return Object.fromEntries(Object.keys(VOICE_TAG_CHOICES).map(key => [
    key, document.getElementById(`voice-new-${key}`).value,
  ]));
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

async function playVoiceUrl(url) {
  voiceLibraryAudio.pause();
  voiceLibraryAudio.src = url;
  document.getElementById('stop-voice-audio').disabled = false;
  try {
    await voiceLibraryAudio.play();
  } catch (error) {
    document.getElementById('stop-voice-audio').disabled = true;
    throw error;
  }
}

voiceLibraryAudio.addEventListener('ended', () => {
  document.getElementById('stop-voice-audio').disabled = true;
});
document.getElementById('stop-voice-audio').addEventListener('click', () => {
  voiceLibraryAudio.pause();
  voiceLibraryAudio.currentTime = 0;
  document.getElementById('stop-voice-audio').disabled = true;
});

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
  const card = document.createElement('div');
  card.className = 'voice-library-card';
  for (const key of Object.keys(VOICE_TAG_CHOICES)) card.dataset[key] = voice[key] || 'unknown';
  const name = document.createElement('input');
  name.className = 'text-input';
  name.value = voice.name;
  name.maxLength = 80;
  name.setAttribute('aria-label', `${voice.name} name`);
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
  actions.appendChild(voiceButton('▶ Preview', async () => {
    try {
      await waitForVoiceModel();
      voiceMessage(`Generating preview: ${voice.name}…`);
      const result = await voiceResponse(await fetch(`/api/voices/${voice.id}/preview`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text: document.getElementById('synthetic-sample-text').value.trim()}),
      }));
      await playVoiceUrl(result.audio_url);
      voiceMessage(`Playing: ${voice.name}`);
    } catch (error) { voiceMessage(error.message, true); }
  }));
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
  card.append(name, transcript, tags, actions);
  return card;
}

document.getElementById('generate-synthetic-voice').addEventListener('click', async () => {
  const button = document.getElementById('generate-synthetic-voice');
  button.disabled = true;
  button.classList.add('is-loading');
  syntheticCandidateId = null;
  document.getElementById('save-synthetic-voice').disabled = true;
  document.getElementById('play-synthetic-candidate').disabled = true;
  try {
    await waitForVoiceModel();
    voiceMessage('Generating a new synthetic voice candidate…');
    const result = await voiceResponse(await fetch('/api/voices/synthetic/candidates', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: document.getElementById('synthetic-sample-text').value.trim()}),
    }));
    syntheticCandidateId = result.candidate_id;
    document.getElementById('play-synthetic-candidate').disabled = false;
    document.getElementById('save-synthetic-voice').disabled = false;
    try {
      await playVoiceUrl(result.audio_url);
      voiceMessage('Candidate ready. Listen, name it, then save it — or generate another.');
    } catch (_) {
      voiceMessage('Candidate ready. Click Play candidate to listen before saving.');
    }
  } catch (error) { voiceMessage(error.message, true); }
  finally { button.disabled = false; button.classList.remove('is-loading'); }
});

document.getElementById('play-synthetic-candidate').addEventListener('click', async () => {
  if (!syntheticCandidateId) return;
  try { await playVoiceUrl(`/api/audio/${syntheticCandidateId}`); }
  catch (error) { voiceMessage(error.message, true); }
});

document.getElementById('save-synthetic-voice').addEventListener('click', async () => {
  if (!syntheticCandidateId) return;
  try {
    const result = await voiceResponse(await fetch('/api/voices/synthetic', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        name: document.getElementById('synthetic-voice-name').value.trim(),
        candidate_id: syntheticCandidateId,
        ...newVoiceTags(),
      }),
    }));
    voiceMessage(`Saved synthetic voice: ${result.name}.`);
    document.getElementById('synthetic-voice-name').value = '';
    clearVoiceFilters();
    await loadVoiceLibrary();
  } catch (error) { voiceMessage(error.message, true); }
});

document.getElementById('save-reference-voice').addEventListener('click', async () => {
  const file = document.getElementById('reference-voice-file').files?.[0];
  const form = new FormData();
  form.append('name', document.getElementById('reference-voice-name').value.trim());
  form.append('ref_text', document.getElementById('reference-voice-text').value.trim());
  for (const [key, value] of Object.entries(newVoiceTags())) form.append(key, value);
  if (file) form.append('file', file);
  try {
    const result = await voiceResponse(await fetch('/api/voices/reference', {
      method: 'POST', body: form,
    }));
    voiceMessage(`Saved reference voice: ${result.name}.`);
    document.getElementById('reference-voice-name').value = '';
    document.getElementById('reference-voice-text').value = '';
    document.getElementById('reference-voice-file').value = '';
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
