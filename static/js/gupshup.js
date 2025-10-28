let ws = null;
let currentGroup = null;
let userId = null;
let userName = null;
let userPhoto = null;
let typingTimeout = null;
let currentTheme = 'light';

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
        if (user && user.id) {
            // ALWAYS use fresh Telegram ID - never use cached values for Telegram users
            return user.id;
        }
    }
    
    // Only for testing outside Telegram - use a persistent ID from localStorage
    let testUserId = localStorage.getItem('gupshup-user-id');
    if (!testUserId) {
        testUserId = 'test_' + Math.floor(Math.random() * 1000000);
        localStorage.setItem('gupshup-user-id', testUserId);
    }
    return testUserId;
}

function setTheme(theme) {
    currentTheme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('gupshup-theme', theme);
    
    document.querySelectorAll('.theme-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-theme-btn="${theme}"]`)?.classList.add('active');
}

function loadTheme() {
    const savedTheme = localStorage.getItem('gupshup-theme') || 'light';
    setTheme(savedTheme);
}

// Profile data persistence using localStorage
function saveProfileToLocalStorage() {
    localStorage.setItem('gupshup-profile-name', userName || '');
    localStorage.setItem('gupshup-profile-photo', userPhoto || '');
}

function loadProfileFromLocalStorage() {
    const savedName = localStorage.getItem('gupshup-profile-name');
    const savedPhoto = localStorage.getItem('gupshup-profile-photo');
    
    if (savedName) {
        userName = savedName;
    }
    if (savedPhoto) {
        userPhoto = savedPhoto;
    }
    
    return { name: savedName, photo: savedPhoto };
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
    document.getElementById('messages-container').innerHTML = '<div class="loading-indicator">Loading messages...</div>';
    
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
    
    const optimisticMessage = {
        user_id: userId,
        user_name: userName,
        user_photo: userPhoto || '/static/images/default-avatar.svg',
        text: text,
        timestamp: new Date().toISOString()
    };
    
    addMessage(optimisticMessage);
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            action: 'message',
            user_id: userId,
            group: currentGroup,
            text: text
        }));
    }
    
    input.value = '';
}

function addMessage(message) {
    const container = document.getElementById('messages-container');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message';
    
    if (String(message.user_id) === String(userId)) {
        messageDiv.classList.add('own');
    }
    
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
    
    if (messages.length === 0) {
        container.innerHTML = '<div class="empty-state">No messages yet. Be the first to say hi! 👋</div>';
    } else {
        messages.forEach(msg => addMessage(msg));
    }
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
    const localProfile = loadProfileFromLocalStorage();
    
    if (localProfile.name) {
        userName = localProfile.name;
        userPhoto = localProfile.photo;
        updateProfilePreview();
    }
    
    try {
        const response = await fetch(`/api/user?user_id=${userId}`);
        if (response.ok) {
            const data = await response.json();
            
            if (!localProfile.name) {
                userName = data.display_name;
                userPhoto = data.photo_url;
                saveProfileToLocalStorage();
            }
            
            updateProfilePreview();
        }
    } catch (error) {
        console.error('Failed to load user data:', error);
        if (!userName) {
            userName = 'User' + userId;
            saveProfileToLocalStorage();
        }
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
        
        saveProfileToLocalStorage();
        
        try {
            await fetch('/api/user/update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: userId,
                    display_name: userName,
                    photo_url: userPhoto
                })
            });
        } catch (error) {
            console.error('Failed to update profile:', error);
        }
        
        updateProfilePreview();
        showScreen('groupSelection');
    }
}

function scrollToBottom() {
    const container = document.getElementById('messages-container');
    container.scrollTop = container.scrollHeight;
}

document.addEventListener('DOMContentLoaded', () => {
    userId = getUserIdFromTelegram();
    
    loadTheme();
    initWebSocket();
    loadUserData();
    
    document.querySelectorAll('.theme-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const theme = btn.dataset.themeBtn;
            setTheme(theme);
        });
    });
    
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
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
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
                saveProfileToLocalStorage();
            }
        }
    });
    
    document.getElementById('refresh-chat-btn').addEventListener('click', () => {
        scrollToBottom();
    });
    
    document.getElementById('attach-btn').addEventListener('click', () => {
        document.getElementById('image-upload').click();
    });
    
    document.getElementById('image-upload').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
            const optimisticImageMessage = {
                user_id: userId,
                user_name: userName,
                user_photo: userPhoto || '/static/images/default-avatar.svg',
                image_url: URL.createObjectURL(file),
                timestamp: new Date().toISOString()
            };
            
            addMessage(optimisticImageMessage);
            
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
});
