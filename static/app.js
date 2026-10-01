let selectedMeetingId = null;
let refreshTimer = null;

const uploadForm = document.getElementById('uploadForm');
const audioFileInput = document.getElementById('audioFile');
const fileDrop = document.querySelector('.file-drop');
const fileTitle = document.querySelector('.file-title');
const fileSubtitle = document.querySelector('.file-subtitle');
const uploadStatus = document.getElementById('uploadStatus');
const meetingsList = document.getElementById('meetingsList');
const meetingDetails = document.getElementById('meetingDetails');
const refreshButton = document.getElementById('refreshButton');
const queryForm = document.getElementById('queryForm');
const questionInput = document.getElementById('questionInput');
const queryAnswer = document.getElementById('queryAnswer');
const querySources = document.getElementById('querySources');

function formatDate(value) {
  if (!value) {
    return 'Unknown time';
  }
  return new Date(value).toLocaleString();
}

function setMessage(target, message, type = '') {
  target.textContent = message;
  target.className = type ? `${target.className.split(' ')[0]} ${type}` : target.className.split(' ')[0];
}

function resetUploadPicker() {
  audioFileInput.value = '';
  fileTitle.textContent = 'Choose a recording';
  fileSubtitle.textContent = 'Drop an audio file here or click to browse.';
}

function showSelectedFile(file) {
  fileTitle.textContent = file.name;
  fileSubtitle.textContent = `${Math.round(file.size / 1024)} KB selected`;
}

function normalizeText(value) {
  return value ? String(value).replace(/\n+/g, '<br />') : '';
}

function renderList(items, emptyLabel) {
  if (!items.length) {
    return emptyLabel;
  }
  return items.map((item) => `• ${item}`).join('<br />');
}

function renderActionItems(actionItems) {
  if (!actionItems.length) {
    return 'No action items extracted yet.';
  }

  return actionItems
    .map((item) => {
      const bits = [item.task];
      if (item.assignee) bits.push(`Owner: ${item.assignee}`);
      if (item.deadline) bits.push(`Deadline: ${item.deadline}`);
      if (item.priority) bits.push(`Priority: ${item.priority}`);
      if (item.status) bits.push(`Status: ${item.status}`);
      return `• ${bits.join(' · ')}`;
    })
    .join('<br />');
}

function shouldAutoRefresh(meetings) {
  return meetings.some((meeting) => meeting.status === 'queued' || meeting.status === 'processing');
}

function startAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
  }

  refreshTimer = setInterval(async () => {
    const response = await fetch('/api/meetings');
    const meetings = await response.json();
    if (shouldAutoRefresh(meetings)) {
      await fetchMeetings();
      if (selectedMeetingId) {
        await selectMeeting(selectedMeetingId, false);
      }
    }
  }, 8000);
}

async function fetchMeetings() {
  meetingsList.innerHTML = '<tr><td colspan="4"><div class="status-box">Loading meetings...</div></td></tr>';
  const response = await fetch('/api/meetings');
  const meetings = await response.json();

  if (!meetings.length) {
    meetingsList.innerHTML = '<tr><td colspan="4"><div class="status-box">No meetings uploaded yet.</div></td></tr>';
    return;
  }

  meetingsList.innerHTML = '';
  meetings.forEach((meeting) => {
    const row = document.createElement('tr');
    if (meeting.id === selectedMeetingId) {
      row.classList.add('selected-row');
    }

    row.innerHTML = `
      <td>
        <button class="row-link" type="button">${meeting.filename}</button>
      </td>
      <td><span class="status-pill ${meeting.status}">${meeting.status}</span></td>
      <td>${formatDate(meeting.created_at)}</td>
      <td>
        <div class="row-actions">
          <button class="secondary-btn" type="button">Open</button>
          <button class="danger-btn" type="button">Delete</button>
        </div>
      </td>
    `;

    const openButton = row.querySelector('.secondary-btn');
    const fileButton = row.querySelector('.row-link');
    const deleteButton = row.querySelector('.danger-btn');
    fileButton.addEventListener('click', () => selectMeeting(meeting.id));
    openButton.addEventListener('click', () => selectMeeting(meeting.id));
    deleteButton.addEventListener('click', () => deleteMeeting(meeting.id));
    meetingsList.appendChild(row);
  });

  startAutoRefresh();
}

async function deleteMeeting(meetingId) {
  const response = await fetch(`/api/meetings/${meetingId}`, { method: 'DELETE' });
  if (!response.ok) {
    const error = await response.json();
    alert(error.detail || 'Could not delete meeting.');
    return;
  }

  if (selectedMeetingId === meetingId) {
    selectedMeetingId = null;
    meetingDetails.innerHTML = 'Select a meeting to see its transcript, summary, and extracted action items.';
    queryAnswer.textContent = 'Ask a question after selecting a completed meeting.';
    querySources.textContent = 'No sources yet.';
    questionInput.value = '';
  }

  await fetchMeetings();
}

async function selectMeeting(meetingId, updateQuestion = true) {
  selectedMeetingId = meetingId;
  queryAnswer.textContent = 'Loading meeting details...';
  querySources.textContent = 'Loading sources...';

  await fetchMeetings();

  const response = await fetch(`/api/meetings/${meetingId}`);
  const meeting = await response.json();

  const analysis = meeting.analysis || {};
  const actionItems = Array.isArray(analysis.action_items) ? analysis.action_items : [];
  const decisions = Array.isArray(analysis.decisions) ? analysis.decisions : [];
  const blockers = Array.isArray(analysis.risks_blockers) ? analysis.risks_blockers : [];
  const unresolved = Array.isArray(analysis.unresolved_items) ? analysis.unresolved_items : [];
  const participants = Array.isArray(analysis.participants) ? analysis.participants : [];

  meetingDetails.innerHTML = `
    <div class="detail-card">
      <strong>${meeting.filename}</strong><br />
      Status: ${meeting.status}<br />
      Created: ${formatDate(meeting.created_at)}
      ${analysis.confidence !== undefined ? `<br />Confidence: ${analysis.confidence}` : ''}
      ${meeting.error_message ? `<br /><span class="error-box">Error: ${meeting.error_message}</span>` : ''}
    </div>
    <div class="detail-card" style="margin-top: 12px;">
      <strong>Summary</strong><br />
      ${normalizeText(meeting.summary) || 'No summary yet.'}
    </div>
    <div class="detail-card" style="margin-top: 12px;">
      <strong>Transcript</strong><br />
      ${normalizeText(meeting.transcript) || 'No transcript yet.'}
    </div>
    <div class="detail-card" style="margin-top: 12px;">
      <strong>Decisions</strong><br />
      ${renderList(decisions, 'No decisions extracted yet.')}
    </div>
    <div class="detail-card" style="margin-top: 12px;">
      <strong>Action items</strong><br />
      ${renderActionItems(actionItems)}
    </div>
    <div class="detail-card" style="margin-top: 12px;">
      <strong>Blockers</strong><br />
      ${renderList(blockers, 'No blockers extracted yet.')}
    </div>
    <div class="detail-card" style="margin-top: 12px;">
      <strong>Unresolved items</strong><br />
      ${renderList(unresolved, 'No unresolved items extracted yet.')}
    </div>
    <div class="detail-card" style="margin-top: 12px;">
      <strong>Participants</strong><br />
      ${participants.length ? participants.join(', ') : 'No participants extracted yet.'}
    </div>
  `;

  if (updateQuestion && questionInput.value.trim()) {
    questionInput.focus();
  }
}

uploadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const file = audioFileInput.files[0];

  if (!file) {
    setMessage(uploadStatus, 'Choose a file first.', 'error-box');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  setMessage(uploadStatus, 'Uploading and starting processing...', 'success-box');

  const response = await fetch('/api/meetings/upload', {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    setMessage(uploadStatus, error.detail || 'Upload failed.', 'error-box');
    return;
  }

  const payload = await response.json();
  setMessage(uploadStatus, `Meeting ${payload.meeting_id} is queued for processing.`, 'success-box');
  resetUploadPicker();
  selectedMeetingId = payload.meeting_id;
  await fetchMeetings();
  await selectMeeting(payload.meeting_id);
});

audioFileInput.addEventListener('click', () => {
  audioFileInput.value = '';
});

fileDrop.addEventListener('pointerdown', () => {
  audioFileInput.value = '';
});

fileDrop.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' || event.key === ' ') {
    audioFileInput.value = '';
  }
});

audioFileInput.addEventListener('change', () => {
  const file = audioFileInput.files[0];
  if (file) {
    showSelectedFile(file);
    return;
  }

  resetUploadPicker();
});

refreshButton.addEventListener('click', fetchMeetings);

queryForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  if (!selectedMeetingId) {
    queryAnswer.textContent = 'Select a meeting first.';
    return;
  }

  const question = questionInput.value.trim();
  if (!question) {
    queryAnswer.textContent = 'Type a question first.';
    return;
  }

  queryAnswer.textContent = 'Thinking...';
  querySources.textContent = 'Loading sources...';

  const response = await fetch(`/api/meetings/${selectedMeetingId}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    const error = await response.json();
    queryAnswer.textContent = error.detail || 'Could not answer the question.';
    querySources.textContent = 'No sources.';
    return;
  }

  const result = await response.json();
  queryAnswer.textContent = result.answer;
  querySources.innerHTML = result.sources.length
    ? result.sources.map((source) => `<span class="source-chip">${source}</span>`).join('')
    : '<span class="source-chip">No sources returned</span>';
});

fetchMeetings().catch((error) => {
  meetingsList.innerHTML = `<tr><td colspan="4"><div class="status-box error-box">Failed to load meetings: ${error.message}</div></td></tr>`;
});
