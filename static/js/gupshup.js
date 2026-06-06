/* ══════════════════════════════════════════════════════
   GUPSHUP — Modern Chat JS
══════════════════════════════════════════════════════ */
'use strict';

/* ── State ─────────────────────────────────────────── */
let ws            = null;
let currentGroup  = null;
let userId        = null;
let userName      = null;
let userPhoto     = null;
let typingTimeout = null;
let reconnectTimer= null;
let reconnectDelay= 1500;
let emojiOpen     = false;
let lastMsgUserId = null;
let isNearBottom  = true;
let drawerOpen    = false;

/* ── Emoji set ─────────────────────────────────────── */
const EMOJIS = [
  '😀','😂','😍','🥰','😎','🤩','😜','😏',
  '🤔','😅','😭','😤','🥺','😴','🤗','😇',
  '👍','👎','❤️','🔥','💯','✨','🎉','🎊',
  '🙏','👏','💪','🤝','👀','🫡','💀','🤣',
  '🌟','💫','⚡','🎯','🏆','🥇','💡','🔮',
  '🍕','🎮','🎵','🎶','📸','🚀','🌈','🤖',
];

/* ── DOM helpers ────────────────────────────────────── */
const $ = id => document.getElementById(id);

const screens = {
  groupSelection: $('group-selection'),
  chatScreen:     $('chat-screen'),
};

/* ══════════════════════════════════════════════════════
   UTILITIES
══════════════════════════════════════════════════════ */
function escapeHtml(t) {
  const d = document.createElement('div');
  d.textContent = t ?? '';
  return d.innerHTML;
}

function formatTime(iso) {
  const d = iso ? new Date(iso) : new Date();
  if (isNaN(d)) return '';
  return d.toLocaleTimeString('en-US', {hour:'2-digit', minute:'2-digit'});
}

function isDefaultName(n) { return !n || /^User\S+/.test(n); }

/* ── Toasts ─────────────────────────────────────────── */
function showToast(text, type = 'info', duration = 2800) {
  const c = $('toast-container');
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = text;
  c.appendChild(t);
  setTimeout(() => {
    t.classList.add('fade-out');
    setTimeout(() => t.remove(), 300);
  }, duration);
}

/* ── Lightbox ──────────────────────────────────────── */
function openLightbox(src) {
  $('lightbox-img').src = src;
  $('lightbox').classList.add('open');
}
$('lightbox').addEventListener('click', e => {
  if (e.target === $('lightbox') || e.target === $('lightbox-close'))
    $('lightbox').classList.remove('open');
});

/* ══════════════════════════════════════════════════════
   THEME
══════════════════════════════════════════════════════ */
function setTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  localStorage.setItem('gupshup-theme', t);
  document.querySelectorAll('[data-theme-btn]').forEach(b =>
    b.classList.toggle('active', b.dataset.themeBtn === t)
  );
}
function loadTheme() { setTheme(localStorage.getItem('gupshup-theme') || 'light'); }

/* ══════════════════════════════════════════════════════
   SCREEN NAVIGATION
══════════════════════════════════════════════════════ */
function showScreen(name) {
  Object.values(screens).forEach(s => s.classList.remove('active'));
  screens[name].classList.add('active');
  if (name === 'chatScreen') updateScrollBtn();
}

/* ══════════════════════════════════════════════════════
   PROFILE DRAWER
══════════════════════════════════════════════════════ */
function openDrawer() {
  drawerOpen = true;
  $('profile-drawer').classList.add('open');
  $('drawer-overlay').classList.add('open');
  /* Sync current values into drawer */
  $('display-name-input').value = userName || '';
  $('edit-photo-preview').src   = userPhoto || '/static/images/default-avatar.svg';
}

function closeDrawer() {
  drawerOpen = false;
  $('profile-drawer').classList.remove('open');
  $('drawer-overlay').classList.remove('open');
}

/* ══════════════════════════════════════════════════════
   USER DATA
══════════════════════════════════════════════════════ */
function getTelegramUser() {
  try {
    if (window.Telegram?.WebApp) {
      window.Telegram.WebApp.expand();
      return window.Telegram.WebApp.initDataUnsafe?.user ?? null;
    }
  } catch(_) {}
  return null;
}

function getOrCreateUserId() {
  const tg = getTelegramUser();
  if (tg?.id) return String(tg.id);
  let id = localStorage.getItem('gupshup-uid');
  if (!id) { id = 'g_' + Math.floor(Math.random()*9e6+1e6); localStorage.setItem('gupshup-uid', id); }
  return id;
}

async function loadUserData() {
  try {
    const tg  = getTelegramUser();
    let url   = `/api/user?user_id=${encodeURIComponent(userId)}`;
    if (tg) {
      const full = [tg.first_name, tg.last_name].filter(Boolean).join(' ');
      if (full)         url += `&first_name=${encodeURIComponent(full)}`;
      if (tg.username)  url += `&username=${encodeURIComponent(tg.username)}`;
      if (tg.photo_url) url += `&photo_url=${encodeURIComponent(tg.photo_url)}`;
    }
    const r = await fetch(url);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    userName  = d.display_name;
    userPhoto = d.photo_url;
    applyProfileUI();
    if (isDefaultName(userName)) openDrawer();   /* new user → open drawer */
  } catch(e) {
    console.error('loadUserData:', e);
    userName  = 'User' + userId.slice(-4);
    userPhoto = '';
    applyProfileUI();
    openDrawer();
  }
}

function applyProfileUI() {
  /* top-right avatar trigger */
  $('preview-photo').src = userPhoto || '/static/images/default-avatar.svg';
  /* hero greeting */
  $('preview-name').textContent = userName ? `Hey, ${userName} 👋` : 'Loading…';
  /* drawer inputs */
  $('edit-photo-preview').src   = userPhoto || '/static/images/default-avatar.svg';
  $('display-name-input').value = userName || '';
}

async function saveProfile() {
  const newName = $('display-name-input').value.trim();
  if (!newName) { showToast('Please enter a display name', 'info'); return; }

  const btn = $('save-profile-btn');
  btn.textContent = 'Saving…'; btn.disabled = true;

  try {
    const r = await fetch('/api/user/update', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ user_id:userId, display_name:newName, photo_url:userPhoto || '' })
    });
    const d = await r.json();
    if (!r.ok || d.error) throw new Error(d.error || 'Server error');
    userName = newName;
    applyProfileUI();
    closeDrawer();
    showToast('Profile saved ✓', 'join');
  } catch(e) {
    showToast('Save failed: ' + e.message, 'info');
  } finally {
    btn.textContent = 'Save Changes'; btn.disabled = false;
  }
}

async function uploadImage(file) {
  const fd = new FormData(); fd.append('image', file);
  try {
    const r = await fetch('/upload', {method:'POST', body:fd});
    if (r.ok) { const d = await r.json(); return d.url ?? null; }
  } catch(e) { console.error('upload:', e); }
  return null;
}

/* ══════════════════════════════════════════════════════
   WEBSOCKET
══════════════════════════════════════════════════════ */
function initWebSocket() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.onopen = () => {
    reconnectDelay = 1500;
    $('conn-banner').classList.remove('show');
    if (currentGroup && userId) sendRaw({action:'join', user_id:userId, group:currentGroup});
  };
  ws.onmessage = e => { try { handleMsg(JSON.parse(e.data)); } catch(_) {} };
  ws.onclose = ws.onerror = () => {
    ws = null;
    if (currentGroup) $('conn-banner').classList.add('show');
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => {
      initWebSocket();
      reconnectDelay = Math.min(reconnectDelay * 1.5, 10000);
    }, reconnectDelay);
  };
}

function sendRaw(obj) {
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function handleMsg(data) {
  switch(data.type) {
    case 'history':
      renderHistory(data.messages || []);
      if (data.online_count !== undefined) setOnlineCount(data.online_count);
      break;
    case 'new_message':
      appendMessage(data.message);
      break;
    case 'user_joined':
      showToast(`${data.user?.name || 'Someone'} joined`, 'join', 2200);
      if (data.online_count !== undefined) setOnlineCount(data.online_count);
      break;
    case 'user_left':
      showToast(`${data.user?.name || 'Someone'} left`, 'leave', 2200);
      if (data.online_count !== undefined) setOnlineCount(data.online_count);
      break;
    case 'typing':
      revealTyping(data.user_name);
      break;
    case 'profile_updated':
      if (String(data.user_id) === String(userId)) {
        userName = data.name; userPhoto = data.photo; applyProfileUI();
      }
      document.querySelectorAll('.message').forEach(el => {
        if (String(el.dataset.uid) === String(data.user_id)) {
          const nm = el.querySelector('.message-name');
          const av = el.querySelector('.message-avatar');
          if (nm) nm.textContent = data.name;
          if (av && data.photo) av.src = data.photo;
        }
      });
      break;
  }
}

/* ══════════════════════════════════════════════════════
   GROUP JOIN / LEAVE
══════════════════════════════════════════════════════ */
function joinGroup(name) {
  currentGroup  = name;
  lastMsgUserId = null;
  $('group-title').textContent  = name;
  $('group-avatar').src         = '/static/images/default-avatar.svg';
  setOnlineCount(0);
  showScreen('chatScreen');

  const c = $('messages-container');
  c.innerHTML = '';
  const spin = document.createElement('div');
  spin.className = 'loading-spinner';
  spin.innerHTML = '<div class="spinner-ring"></div><div class="spinner-text">Loading messages…</div>';
  c.appendChild(spin);

  if (!ws || ws.readyState !== WebSocket.OPEN) initWebSocket();
  else sendRaw({action:'join', user_id:userId, group:name});
}

function leaveGroup() {
  if (currentGroup) {
    sendRaw({action:'leave', user_id:userId, group:currentGroup});
    currentGroup  = null;
    lastMsgUserId = null;
  }
  $('conn-banner').classList.remove('show');
  showScreen('groupSelection');
}

function setOnlineCount(n) {
  $('online-count').textContent = `● ${n} member${n !== 1 ? 's' : ''} online`;
}

/* ══════════════════════════════════════════════════════
   MESSAGES
══════════════════════════════════════════════════════ */
function renderHistory(msgs) {
  const c = $('messages-container');
  c.innerHTML = ''; lastMsgUserId = null;
  if (!msgs.length) {
    c.innerHTML = `<div class="empty-state">
      <div class="empty-icon">💬</div>
      <div class="empty-text">No messages yet</div>
      <div class="empty-sub">Be the first to say hi! 👋</div>
    </div>`;
    return;
  }
  msgs.forEach(m => appendMessage(m, false));
  scrollBottom(false);
}

function appendMessage(msg, animate = true) {
  const c = $('messages-container');
  const empty = c.querySelector('.empty-state, .loading-spinner');
  if (empty) empty.remove();

  const isOwn  = String(msg.user_id) === String(userId);
  const consec = String(msg.user_id) === String(lastMsgUserId);
  lastMsgUserId = String(msg.user_id);

  const time   = formatTime(msg.timestamp);
  const avatar = msg.user_photo || '/static/images/default-avatar.svg';
  const name   = msg.user_name  || 'Anonymous';

  const wrapper = document.createElement('div');
  wrapper.className = `message${isOwn ? ' own' : ''}${consec ? ' consecutive' : ''}`;
  wrapper.dataset.uid = String(msg.user_id);
  if (!animate) wrapper.style.animation = 'none';

  let bubbleContent = '';
  if (msg.text)      bubbleContent += `<span>${escapeHtml(msg.text)}</span>`;
  if (msg.image_url) bubbleContent += `<img src="${msg.image_url}" alt="Image" loading="lazy" class="msg-img">`;
  if (msg.gif_url)   bubbleContent += `<img src="${msg.gif_url}"   alt="GIF"   loading="lazy" class="msg-img">`;

  const tailClass = isOwn ? 'tail-out' : 'tail-in';

  wrapper.innerHTML = `
    <img src="${avatar}" alt="${escapeHtml(name)}" class="message-avatar">
    <div class="message-content">
      ${!consec ? `<div class="message-meta">
        <span class="message-name">${escapeHtml(name)}</span>
        <span class="message-time">${time}</span>
      </div>` : ''}
      <div class="message-bubble ${tailClass}">
        ${bubbleContent}
        <span class="bubble-time-inline">${time}</span>
      </div>
    </div>`;

  wrapper.querySelector('.message-avatar').addEventListener('click', () =>
    showToast(name, 'info', 1600)
  );
  wrapper.querySelectorAll('.msg-img').forEach(img =>
    img.addEventListener('click', () => openLightbox(img.src))
  );

  c.appendChild(wrapper);
  if (isNearBottom || isOwn) scrollBottom(false);
  updateScrollBtn();
}

/* ══════════════════════════════════════════════════════
   SEND MESSAGE
══════════════════════════════════════════════════════ */
function sendMessage() {
  const input = $('message-input');
  const text  = input.value.trim();
  if (!text || !currentGroup) return;
  appendMessage({user_id:userId, user_name:userName, user_photo:userPhoto, text, timestamp:new Date().toISOString()});
  sendRaw({action:'message', user_id:userId, group:currentGroup, text});
  input.value = '';
  autoResize(input); updateSendBtn();
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 110) + 'px';
}

function updateSendBtn() {
  $('send-btn').classList.toggle('visible', $('message-input').value.trim().length > 0);
}

/* ── Typing ─────────────────────────────────────────── */
let typingSent = false;
function maybeSendTyping() {
  if (typingSent) return; typingSent = true;
  sendRaw({action:'typing', user_id:userId, group:currentGroup});
  setTimeout(() => { typingSent = false; }, 2400);
}
function revealTyping(name) {
  $('typing-text').textContent = `${name} is typing`;
  $('typing-bar').classList.add('visible');
  clearTimeout(typingTimeout);
  typingTimeout = setTimeout(() => $('typing-bar').classList.remove('visible'), 3200);
}

/* ══════════════════════════════════════════════════════
   SCROLL
══════════════════════════════════════════════════════ */
function scrollBottom(smooth = true) {
  const c = $('messages-container');
  c.scrollTo({top:c.scrollHeight, behavior:smooth ? 'smooth' : 'auto'});
}
function updateScrollBtn() {
  const c = $('messages-container');
  const dist = c.scrollHeight - c.scrollTop - c.clientHeight;
  isNearBottom = dist < 80;
  $('scroll-bottom-btn').classList.toggle('visible', dist > 160);
}

/* ══════════════════════════════════════════════════════
   EMOJI PICKER
══════════════════════════════════════════════════════ */
function buildEmojiPicker() {
  const grid = $('emoji-grid');
  EMOJIS.forEach(em => {
    const btn = document.createElement('button');
    btn.className = 'emoji-btn'; btn.textContent = em;
    btn.addEventListener('click', () => {
      const inp = $('message-input');
      const pos = inp.selectionStart ?? inp.value.length;
      inp.value = inp.value.slice(0, pos) + em + inp.value.slice(pos);
      inp.selectionStart = inp.selectionEnd = pos + em.length;
      inp.focus(); autoResize(inp); updateSendBtn();
    });
    grid.appendChild(btn);
  });
}
function toggleEmoji() {
  emojiOpen = !emojiOpen;
  $('emoji-picker').classList.toggle('open', emojiOpen);
}
document.addEventListener('click', e => {
  if (emojiOpen && !$('emoji-picker').contains(e.target) && e.target !== $('emoji-btn')) {
    emojiOpen = false; $('emoji-picker').classList.remove('open');
  }
});

/* ══════════════════════════════════════════════════════
   INIT
══════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  userId = getOrCreateUserId();
  loadTheme();
  buildEmojiPicker();
  initWebSocket();
  loadUserData();

  /* ── Theme buttons (inside drawer) ─────────────── */
  document.querySelectorAll('[data-theme-btn]').forEach(b =>
    b.addEventListener('click', () => setTheme(b.dataset.themeBtn))
  );

  /* ── Group cards ───────────────────────────────── */
  document.querySelectorAll('.group-card').forEach(btn =>
    btn.addEventListener('click', () => joinGroup(btn.dataset.group))
  );

  /* ── Profile trigger (top-right avatar) ─────────── */
  $('profile-trigger').addEventListener('click', () => openDrawer());

  /* ── Drawer close ──────────────────────────────── */
  $('drawer-close-btn').addEventListener('click', closeDrawer);
  $('drawer-overlay').addEventListener('click', closeDrawer);

  /* ── Avatar upload (inside drawer) ─────────────── */
  $('avatar-edit-wrap').addEventListener('click', () => $('photo-upload').click());
  $('photo-upload').addEventListener('change', async e => {
    const file = e.target.files[0]; if (!file) return;
    const url  = await uploadImage(file);
    if (url) { userPhoto = url; $('edit-photo-preview').src = url; $('preview-photo').src = url; showToast('Photo uploaded ✓','join'); }
    else showToast('Upload failed','info');
    e.target.value = '';
  });

  /* ── Save profile ──────────────────────────────── */
  $('save-profile-btn').addEventListener('click', saveProfile);
  $('display-name-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') saveProfile();
  });

  /* ── Chat back ─────────────────────────────────── */
  $('back-btn').addEventListener('click', leaveGroup);

  /* ── Send ──────────────────────────────────────── */
  $('send-btn').addEventListener('click', sendMessage);
  $('message-input').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  $('message-input').addEventListener('input', e => {
    autoResize(e.target); updateSendBtn();
    if (currentGroup) maybeSendTyping();
  });

  /* ── Emoji ─────────────────────────────────────── */
  $('emoji-btn').addEventListener('click', e => { e.stopPropagation(); toggleEmoji(); });

  /* ── Attach image ──────────────────────────────── */
  $('attach-btn').addEventListener('click', () => $('image-upload').click());
  $('image-upload').addEventListener('change', async e => {
    const file = e.target.files[0]; if (!file) return;
    const local = URL.createObjectURL(file);
    appendMessage({user_id:userId, user_name:userName, user_photo:userPhoto, image_url:local, timestamp:new Date().toISOString()});
    const url = await uploadImage(file);
    if (url) sendRaw({action:'message', user_id:userId, group:currentGroup, image_url:url});
    e.target.value = '';
  });

  /* ── Scroll buttons ────────────────────────────── */
  $('refresh-btn').addEventListener('click', () => scrollBottom(true));
  $('scroll-bottom-btn').addEventListener('click', () => scrollBottom(true));
  $('messages-container').addEventListener('scroll', updateScrollBtn, {passive:true});

  /* ── Members badge ─────────────────────────────── */
  $('members-btn').addEventListener('click', () => showToast($('online-count').textContent,'info',2000));

  /* ── Escape key closes drawer ──────────────────── */
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && drawerOpen) closeDrawer(); });
});
