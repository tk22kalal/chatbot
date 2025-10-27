let ws = null;
let currentGroup = null;
let userId = null;
let userName = null;
let userPhoto = null;
let typingTimeout = null;

const screens = {
    groupSelection: document.getElementById('group-selection'),
    chatScreen: document.getElementById('chat-screen'),
    profileEdit: document.getElementById('profile-edit')
};

function getUserIdFromTelegram() {
    if (window.Telegram && window.Telegram.WebApp) {
        const tg = window.Telegram.WebApp;
        tg.expand();
        const user = tg.initDataUnsafe.user;
        if (user) {
            return user.id;
        }
    }
    return Math.floor(Math.random() * 1000000);
}

function showScreen(screenName) {
    Object.values(screens).forEach(screen => screen.classList.remove('active'));
    screens[screenName].classList.add('active');
}

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
        setTimeout(initWebSocket, 3000);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

function handleWebSocketMessage(data) {
    switch(data.type) {
        case 'history':
            displayMessageHistory(data.messages);
            if (data.online_count !== undefined) {
                updateOnlineCount(data.online_count);
            }
            break;
        case 'new_message':
            addMessage(data.message);
            break;
        case 'user_joined':
            showNotification(`${data.user.name} joined the chat`);
            if (data.online_count !== undefined) {
                updateOnlineCount(data.online_count);
            }
            break;
        case 'user_left':
            showNotification(`${data.user.name} left the chat`);
            if (data.online_count !== undefined) {
                updateOnlineCount(data.online_count);
            }
            break;
        case 'typing':
            showTypingIndicator(data.user_name);
            break;
        case 'profile_updated':
            if (data.user_id === userId) {
                userName = data.name;
                userPhoto = data.photo;
                updateProfilePreview();
            }
            break;
    }
}

function updateOnlineCount(count) {
    const onlineCountEl = document.getElementById('online-count');
    if (onlineCountEl) {
        onlineCountEl.textContent = `${count} member${count !== 1 ? 's' : ''} online`;
    }
}

function joinGroup(groupName) {
    currentGroup = groupName;
    document.getElementById('group-title').textContent = groupName;
    document.getElementById('messages-container').innerHTML = '';
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            action: 'join',
            user_id: userId,
            group: groupName
        }));
    }
    
    showScreen('chatScreen');
}

function sendMessage() {
    const input = document.getElementById('message-input');
    const text = input.value.trim();
    
    if (!text || !currentGroup) return;
    
    ws.send(JSON.stringify({
        action: 'message',
        user_id: userId,
        group: currentGroup,
        text: text
    }));
    
    input.value = '';
}

function addMessage(message) {
    const container = document.getElementById('messages-container');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message';
    
    const avatar = message.user_photo || '/static/images/default-avatar.svg';
    const time = new Date(message.timestamp).toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    let contentHTML = '';
    if (message.text) {
        contentHTML = `<div class="message-bubble">${escapeHtml(message.text)}</div>`;
    }
    if (message.image_url) {
        contentHTML += `<div class="message-bubble"><img src="${message.image_url}" alt="Image"></div>`;
    }
    if (message.gif_url) {
        contentHTML += `<div class="message-bubble"><img src="${message.gif_url}" alt="GIF"></div>`;
    }
    
    messageDiv.innerHTML = `
        <img src="${avatar}" alt="Avatar" class="message-avatar">
        <div class="message-content">
            <div class="message-header">
                <span class="message-name">${escapeHtml(message.user_name)}</span>
                <span class="message-time">${time}</span>
            </div>
            ${contentHTML}
        </div>
    `;
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

function displayMessageHistory(messages) {
    const container = document.getElementById('messages-container');
    container.innerHTML = '';
    messages.forEach(msg => addMessage(msg));
}

function showTypingIndicator(userName) {
    const indicator = document.getElementById('typing-indicator');
    indicator.innerHTML = `<span>${escapeHtml(userName)}</span> is typing...`;
    indicator.style.display = 'block';
    
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
        indicator.style.display = 'none';
    }, 3000);
}

function sendTypingIndicator() {
    if (ws && ws.readyState === WebSocket.OPEN && currentGroup) {
        ws.send(JSON.stringify({
            action: 'typing',
            user_id: userId,
            group: currentGroup
        }));
    }
}

function showNotification(text) {
    console.log('Notification:', text);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function loadUserData() {
    try {
        const response = await fetch(`/api/user?user_id=${userId}`);
        if (response.ok) {
            const data = await response.json();
            userName = data.display_name;
            userPhoto = data.photo_url;
            updateProfilePreview();
        }
    } catch (error) {
        console.error('Failed to load user data:', error);
        userName = 'User' + userId;
        updateProfilePreview();
    }
}

function updateProfilePreview() {
    document.getElementById('preview-name').textContent = userName;
    document.getElementById('preview-photo').src = userPhoto || '/static/images/default-avatar.svg';
    document.getElementById('display-name-input').value = userName;
    document.getElementById('edit-photo-preview').src = userPhoto || '/static/images/default-avatar.svg';
}

async function uploadImage(file) {
    const formData = new FormData();
    formData.append('image', file);
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            return data.url;
        }
    } catch (error) {
        console.error('Upload failed:', error);
    }
    return null;
}

async function saveProfile() {
    const newName = document.getElementById('display-name-input').value.trim();
    
    if (newName) {
        userName = newName;
        
        ws.send(JSON.stringify({
            action: 'update_profile',
            user_id: userId,
            name: userName,
            photo_url: userPhoto
        }));
        
        updateProfilePreview();
        showScreen('groupSelection');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    userId = getUserIdFromTelegram();
    
    initWebSocket();
    loadUserData();
    
    document.querySelectorAll('.group-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const group = btn.dataset.group;
            joinGroup(group);
        });
    });
    
    document.getElementById('back-btn').addEventListener('click', () => {
        if (currentGroup) {
            currentGroup = null;
            showScreen('groupSelection');
        }
    });
    
    document.getElementById('send-btn').addEventListener('click', sendMessage);
    
    document.getElementById('message-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
    
    document.getElementById('message-input').addEventListener('input', () => {
        sendTypingIndicator();
    });
    
    document.getElementById('edit-profile-btn').addEventListener('click', () => {
        showScreen('profileEdit');
    });
    
    document.getElementById('profile-back-btn').addEventListener('click', () => {
        showScreen('groupSelection');
    });
    
    document.getElementById('save-profile-btn').addEventListener('click', saveProfile);
    
    document.getElementById('change-photo-btn').addEventListener('click', () => {
        document.getElementById('photo-upload').click();
    });
    
    document.getElementById('photo-upload').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
            const url = await uploadImage(file);
            if (url) {
                userPhoto = url;
                document.getElementById('edit-photo-preview').src = url;
            }
        }
    });
    
    document.getElementById('attach-btn').addEventListener('click', () => {
        document.getElementById('attach-menu').style.display = 'block';
    });
    
    document.getElementById('upload-image-btn').addEventListener('click', () => {
        document.getElementById('image-upload').click();
        document.getElementById('attach-menu').style.display = 'none';
    });
    
    document.getElementById('close-attach-menu').addEventListener('click', () => {
        document.getElementById('attach-menu').style.display = 'none';
    });
    
    document.getElementById('image-upload').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
            const url = await uploadImage(file);
            if (url && ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    action: 'message',
                    user_id: userId,
                    group: currentGroup,
                    image_url: url
                }));
            }
        }
    });
    
    document.getElementById('emoji-btn').addEventListener('click', () => {
        const input = document.getElementById('message-input');
        input.value += '😊';
        input.focus();
    });
});
