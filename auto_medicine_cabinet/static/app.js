const canvasOptions = { type: 'image/jpeg', quality: 0.9 };

async function startCamera(videoId) {
  const video = document.getElementById(videoId);
  if (!video) return null;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
    video.srcObject = stream;
    await video.play();
    return video;
  } catch (err) {
    console.error('Camera error', err);
    return null;
  }
}

function captureBlob(video, canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!video || !canvas) return null;
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  return new Promise(resolve => canvas.toBlob(resolve, canvasOptions.type, canvasOptions.quality));
}

async function scanFace() {
  const video = document.getElementById('scanVideo');
  const blob = await captureBlob(video, 'captureCanvas');
  if (!blob) return;
  const form = new FormData();
  form.append('face', blob, 'scan.jpg');
  setStatus('scanStatus', 'Processing scan...', '');
  const res = await fetch('/api/scan', { method: 'POST', body: form });
  const data = await res.json();
  if (!res.ok) {
    setStatus('scanStatus', data.error || 'Scan failed', 'error');
    return;
  }
  const user = data.user || {};
  document.getElementById('scanUser').textContent = user.name || 'Unknown';
  document.getElementById('scanEmail').textContent = user.email || '-';
  document.getElementById('scanScore').textContent = data.score ? data.score.toFixed(3) : '-';
  setStatus('scanStatus', 'User recognized', 'success');
}

async function registerUser(evt) {
  evt.preventDefault();
  const video = document.getElementById('registerVideo');
  const blob = await captureBlob(video, 'registerCanvas');
  const form = new FormData(evt.target);
  if (blob) {
    form.append('face', blob, 'register.jpg');
  } else {
    const fileInput = document.getElementById('faceFile');
    if (fileInput.files[0]) {
      form.append('face', fileInput.files[0]);
    }
  }
  setStatus('registerStatus', 'Submitting registration...', '');
  const res = await fetch('/api/register', { method: 'POST', body: form });
  const data = await res.json();
  if (!res.ok) {
    setStatus('registerStatus', data.error || 'Registration failed', 'error');
    return;
  }
  setStatus('registerStatus', `Registered ${data.user.name}`, 'success');
  evt.target.reset();
}

async function sendOrder(evt) {
  evt.preventDefault();
  const payload = Object.fromEntries(new FormData(evt.target).entries());
  payload.quantity = Number(payload.quantity || 1);
  setStatus('orderStatus', 'Sending order...', '');
  const res = await fetch('/api/order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok) {
    setStatus('orderStatus', data.error || 'Order failed', 'error');
    return;
  }
  setStatus('orderStatus', `Order placed for ${data.order.medicine}`, 'success');
}

async function refreshDashboard() {
  const res = await fetch('/api/dashboard');
  const data = await res.json();
  renderUsers(data.users || []);
  renderStock(data.stock || {});
  renderOrders(data.orders || []);
  const serialStatus = document.getElementById('serialStatus');
  if (serialStatus) {
    serialStatus.textContent = data.serial_connected ? 'Dispenser connected' : 'Dispenser offline';
    serialStatus.className = data.serial_connected ? 'status success' : 'status error';
  }
}

function renderUsers(users) {
  const list = document.getElementById('usersList');
  if (!list) return;
  list.innerHTML = '';
  users.forEach(u => {
    const div = document.createElement('div');
    div.className = 'item';
    div.innerHTML = `<strong>${u.name}</strong><div class="meta">${u.email} · ${u.id}</div>`;
    list.appendChild(div);
  });
}

function renderStock(stock) {
  const list = document.getElementById('stockList');
  if (!list) return;
  list.innerHTML = '';
  Object.entries(stock).forEach(([name, info]) => {
    const div = document.createElement('div');
    div.className = 'item';
    div.innerHTML = `<strong>${name}</strong><div class="meta">Qty: ${info.quantity} · Dispense: ${info.dispense_code || '-'} </div>`;
    list.appendChild(div);
  });
}

function renderOrders(orders) {
  const list = document.getElementById('ordersList');
  if (!list) return;
  list.innerHTML = '';
  orders.slice().reverse().forEach(o => {
    const div = document.createElement('div');
    div.className = 'item';
    div.innerHTML = `<strong>${o.medicine} x${o.quantity}</strong><div class="meta">${o.user_id} · ${new Date(o.ordered_at).toLocaleString()}</div>`;
    list.appendChild(div);
  });
}

function setStatus(id, text, type) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className = `status ${type || ''}`.trim();
}

function bindIndex() {
  const scanBtn = document.getElementById('scanBtn');
  startCamera('scanVideo');
  if (scanBtn) scanBtn.addEventListener('click', scanFace);
}

function bindRegister() {
  startCamera('registerVideo');
  const form = document.getElementById('registerForm');
  if (form) form.addEventListener('submit', registerUser);
  const capture = document.getElementById('captureRegister');
  if (capture) capture.addEventListener('click', () => captureBlob(document.getElementById('registerVideo'), 'registerCanvas'));
}

function bindDashboard() {
  const form = document.getElementById('orderForm');
  if (form) form.addEventListener('submit', sendOrder);
  refreshDashboard();
  setInterval(refreshDashboard, 1000);
}

document.addEventListener('DOMContentLoaded', () => {
  const page = document.body.dataset.page;
  if (page === 'index') bindIndex();
  if (page === 'register') bindRegister();
  if (page === 'dashboard') bindDashboard();
});
