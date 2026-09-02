const messages = document.querySelector('#messages');
const form = document.querySelector('#chat-form');
const input = document.querySelector('#input');
const send = document.querySelector('#send');
const attempts = document.querySelector('#attempts');
const victory = document.querySelector('#victory');
const failure = document.querySelector('#failure');
let sessionId = localStorage.getItem('fatalbot-session');

function addMessage(text, role) {
  const item = document.createElement('div');
  item.className = `message ${role}`;
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = role === 'bot' ? 'FB' : 'YOU';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  renderChatText(bubble, text);
  item.append(avatar, bubble);
  messages.append(item);
  messages.scrollTop = messages.scrollHeight;
  return item;
}

function emojiIcon(type) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.classList.add('inline-emoji');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', type === 'shield' ? 'shield' : 'lock');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  if (type === 'shield') {
    path.setAttribute('d', 'M12 2 20 5v6c0 5.1-3.4 9.4-8 11-4.6-1.6-8-5.9-8-11V5l8-3Zm0 3.1L7 7v4c0 3.4 2 6.5 5 7.8 3-1.3 5-4.4 5-7.8V7l-5-1.9Z');
  } else {
    path.setAttribute('d', 'M17 9h-1V7a4 4 0 0 0-8 0v2H7a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2Zm-6 8.7V19h2v-1.3a2 2 0 1 0-2 0ZM10 9V7a2 2 0 0 1 4 0v2h-4Z');
  }
  svg.append(path);
  return svg;
}

function renderChatText(element, source) {
  // Repair the most common UTF-8-as-Latin-1 forms before icon replacement.
  const text = source
    .replaceAll('ðŸ›¡ï¸\u008f', '🛡️')
    .replaceAll('ðŸ›¡', '🛡️')
    .replaceAll('ðŸ”’', '🔒');
  const parts = text.split(/(🛡️?|🔒)/gu);
  const fragment = document.createDocumentFragment();
  for (const part of parts) {
    if (/^🛡️?$/u.test(part)) fragment.append(emojiIcon('shield'));
    else if (part === '🔒') fragment.append(emojiIcon('lock'));
    else if (part) fragment.append(document.createTextNode(part));
  }
  element.replaceChildren(fragment);
}

async function resetGame() {
  try {
    const response = await fetch('/api/reset', { method: 'POST' });
    const data = await response.json();
    sessionId = data.sessionId;
    localStorage.setItem('fatalbot-session', sessionId);
    attempts.textContent = '0';
    victory.hidden = true;
    failure.hidden = true;
    input.disabled = false;
    send.disabled = false;
    messages.innerHTML = '';
    addMessage("New session. The flag is safe again. What's your best prompt?", 'bot');
    input.focus();
  } catch { addMessage('Could not reset the session.', 'bot'); }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text || send.disabled) return;
  addMessage(text, 'user');
  input.value = '';
  input.style.height = 'auto';
  send.disabled = true;
  const typing = addMessage('thinking', 'bot');
  typing.classList.add('typing');
  const replyBubble = typing.querySelector('.bubble');
  let replyText = '';
  let receivedToken = false;
  let completed = false;
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, message: text })
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Request failed');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const handleEvent = (data) => {
      if (data.type === 'start') {
        sessionId = data.sessionId;
        localStorage.setItem('fatalbot-session', sessionId);
        attempts.textContent = data.attempts;
      } else if (data.type === 'token') {
        if (!receivedToken) {
          receivedToken = true;
          typing.classList.remove('typing');
          replyBubble.textContent = '';
        }
        replyText += data.content;
        renderChatText(replyBubble, replyText);
        messages.scrollTop = messages.scrollHeight;
      } else if (data.type === 'done') {
        completed = true;
        attempts.textContent = data.attempts;
        if (data.roundOver) {
          input.disabled = true;
          setTimeout(() => {
            if (data.won) victory.hidden = false;
            else failure.hidden = false;
          }, 450);
        }
      } else if (data.type === 'error') {
        throw new Error(data.message);
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (line.trim()) handleEvent(JSON.parse(line));
      }
      if (done) break;
    }
    if (buffer.trim()) handleEvent(JSON.parse(buffer));
    if (!completed) throw new Error('The response stream ended unexpectedly');
  } catch (error) {
    if (!receivedToken) typing.remove();
    else typing.classList.remove('typing');
    addMessage(`Connection error: ${error.message}`, 'bot');
  } finally {
    if (!input.disabled) {
      send.disabled = false;
      input.focus();
    }
  }
});

input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
});
input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); }
});
document.querySelector('#reset').addEventListener('click', resetGame);
document.querySelector('#play-again').addEventListener('click', resetGame);
document.querySelector('#next-player').addEventListener('click', resetGame);

fetch('/api/config').then(r => r.json()).then(data => {
  document.querySelector('#club-name').textContent = data.clubName;
  document.querySelector('#welcome').textContent = data.welcome;
  document.querySelector('#max-attempts').textContent = data.maxAttempts;
}).catch(() => {});
