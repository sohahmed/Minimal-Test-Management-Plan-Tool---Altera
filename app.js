let testPlans = [];
let activeTestId = null;

function showUploadModal() {
  document.getElementById('uploadModal').style.display = 'flex';
}
function closeUploadModal() {
  document.getElementById('uploadModal').style.display = 'none';
  document.getElementById('planTitleInput').value = '';
  document.getElementById('fileInput').value = '';
}

function handlePlanUpload() {
  const fileInput = document.getElementById('fileInput');
  if (fileInput.files.length === 0) {
    alert("Please upload a requirement document (.txt, .pdf, .docx).");
    return;
  }
  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append('file', file);

  fetch('http://127.0.0.1:8000/suggest_file', {
    method: 'POST',
    body: formData
  })
  .then(resp => resp.json())
  .then(suggestion => {
    fetch('http://127.0.0.1:8000/testplans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: 0,
        title: suggestion.title,
        description: suggestion.description,
        steps: suggestion.steps.map(s => ({ description: s }))
      })
    })
    .then(r => r.json())
    .then(plan => {
      testPlans.push(plan);
      activeTestId = plan.id;
      renderSidebar();
      renderDetails();
      closeUploadModal();
    });
  });
}

// Remaining CRUD and rendering logic unchanged from prior version
function getActiveTestPlan() {
  return testPlans.find(tp => tp.id === activeTestId);
}
function loadTestPlans() {
  fetch('http://127.0.0.1:8000/testplans')
    .then(r => r.json())
    .then(data => {
      testPlans = data;
      if (testPlans.length) activeTestId = testPlans[0].id;
      renderSidebar();
      renderDetails();
    });
}
function deleteTestPlan(id) {
  fetch(`http://127.0.0.1:8000/testplans/${id}`, { method: 'DELETE' })
    .then(() => {
      testPlans = testPlans.filter(tp => tp.id !== id);
      activeTestId = (testPlans[0] || {}).id || null;
      renderSidebar();
      renderDetails();
    });
}
function addStep() {
  const stepText = document.getElementById('newStepInput').value.trim();
  if (!stepText) return;
  fetch(`http://127.0.0.1:8000/testplans/${activeTestId}/steps`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description: stepText })
  })
    .then(r => r.json())
    .then(steps => {
      getActiveTestPlan().steps = steps;
      renderDetails();
      document.getElementById('newStepInput').value = '';
    });
}
function editStep(idx) {
  const oldTxt = getActiveTestPlan().steps[idx].description;
  const newText = prompt("Edit step:", oldTxt);
  if (!newText || newText === oldTxt) return;
  fetch(`http://127.0.0.1:8000/testplans/${activeTestId}/steps/${idx}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description: newText })
  })
    .then(r => r.json())
    .then(() => {
      getActiveTestPlan().steps[idx].description = newText;
      renderDetails();
    });
}
function deleteStep(idx) {
  fetch(`http://127.0.0.1:8000/testplans/${activeTestId}/steps/${idx}`, { method: 'DELETE' })
    .then(r => r.json())
    .then(() => {
      getActiveTestPlan().steps.splice(idx, 1);
      renderDetails();
    });
}
function renderSidebar() {
  const list = document.getElementById('testList');
  list.innerHTML = '';
  testPlans.forEach(tp => {
    const div = document.createElement('div');
    div.className = 'sidebar-item' + (tp.id === activeTestId ? ' active' : '');
    div.textContent = tp.title;
    div.onclick = () => {
      activeTestId = tp.id;
      renderSidebar();
      renderDetails();
    };
    list.appendChild(div);
  });
}
function renderDetails() {
  const panel = document.getElementById('detailPanel');
  panel.innerHTML = '';
  const tp = getActiveTestPlan();
  if (!tp) {
    panel.innerHTML = '<span class="no-tests">No test case selected</span>';
    return;
  }
  let html = `
    <div class="title-row">
      <span>${tp.title}</span>
      <button class="delete-btn" onclick="deleteTestPlan(${tp.id})">delete</button>
    </div>
    <div class="description-area">
      <b>Description</b>
      <p>${tp.description}</p>
    </div>
    <div class="steps-area">
      <b>Potential Steps</b>
      <ol>
  `;
  tp.steps.forEach((s, idx) =>
    html += `<li>
      ${s.description}
      <button onclick="editStep(${idx})">Edit</button>
      <button onclick="deleteStep(${idx})">Delete</button>
    </li>`
  );
  html += `</ol>
    <input id="newStepInput" type="text" placeholder="Add new step..." style="margin-right:6px;">
    <button onclick="addStep()">Add Step</button>
  </div>`;
  panel.innerHTML = html;
}
window.addEventListener('DOMContentLoaded', () => {
  loadTestPlans();
  document.querySelector('.add-btn').onclick = showUploadModal;
});