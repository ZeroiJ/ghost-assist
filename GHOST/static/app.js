/* Ghost Assistant — Frontend Logic */

(function () {
    'use strict';

    const answersEl = document.getElementById('answers');
    const emptyState = document.getElementById('empty-state');
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const answerCount = document.getElementById('answer-count');
    const manualInput = document.getElementById('manual-input');
    const sendBtn = document.getElementById('send-btn');
    const analyzeBtn = document.getElementById('analyze-btn');

    let eventSource = null;
    let totalAnswers = 0;
    let generatingEl = null;

    // Track in-progress streaming answers by ID
    const streamingCards = {};

    // --- SSE Connection ---
    function connectSSE() {
        if (eventSource) {
            eventSource.close();
        }

        eventSource = new EventSource('/stream');

        eventSource.onmessage = function (event) {
            try {
                const data = JSON.parse(event.data);
                handleEvent(data);
            } catch (e) {
                console.error('SSE parse error:', e);
            }
        };

        eventSource.onerror = function () {
            updateStatus('error');
            // Auto-reconnect after 3s
            setTimeout(connectSSE, 3000);
        };

        eventSource.onopen = function () {
            console.log('SSE connected');
        };
    }

    // --- Event Handlers ---
    function handleEvent(data) {
        switch (data.type) {
            case 'state':
                updateStatus(data.state);
                break;
            case 'answer':
                // Full answer (from history on reconnect)
                addAnswer(data);
                break;
            case 'answer-start':
                startStreamingAnswer(data);
                break;
            case 'answer-chunk':
                appendChunk(data);
                break;
            case 'answer-done':
                finalizeAnswer(data);
                break;
            case 'error':
                showError(data.message);
                break;
        }
    }

    function updateStatus(state) {
        // Update dot class
        statusDot.className = 'dot dot-' + state;
        statusText.textContent = state;

        // Show/remove generating indicator (only if no streaming card is active)
        if (state === 'generating' && Object.keys(streamingCards).length === 0) {
            showGenerating();
        } else if (state !== 'generating') {
            removeGenerating();
        }
    }

    function showGenerating() {
        if (generatingEl) return;
        generatingEl = document.createElement('div');
        generatingEl.className = 'generating-indicator';
        generatingEl.innerHTML = '<span class="generating-dots">Generating</span>';
        answersEl.appendChild(generatingEl);
        scrollToBottom();
    }

    function removeGenerating() {
        if (generatingEl) {
            generatingEl.remove();
            generatingEl = null;
        }
    }

    // --- Streaming Answer Handlers ---
    function startStreamingAnswer(data) {
        // Hide empty state
        if (emptyState) {
            emptyState.style.display = 'none';
        }
        removeGenerating();

        const card = document.createElement('div');
        card.className = 'answer-card streaming';

        const time = new Date(data.timestamp * 1000);
        const timeStr = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const sourceLabel = data.source === 'auto' ? 'AUTO' : data.source === 'screen' ? 'SCREEN' : 'MANUAL';

        card.innerHTML = `
            <div class="answer-meta">
                <span class="answer-source">${sourceLabel} · <span class="answer-ai">...</span></span>
                <span class="answer-time">${timeStr}</span>
            </div>
            <div class="answer-body"><span class="cursor">|</span></div>
        `;

        answersEl.appendChild(card);
        scrollToBottom();

        // Track this streaming card
        streamingCards[data.id] = {
            card: card,
            body: card.querySelector('.answer-body'),
            aiLabel: card.querySelector('.answer-ai'),
            rawText: '',
        };
    }

    function appendChunk(data) {
        const entry = streamingCards[data.id];
        if (!entry) return;

        entry.rawText += data.chunk;

        // Re-render the full text with formatting (cursor at end)
        entry.body.innerHTML = formatAnswer(entry.rawText) + '<span class="cursor">|</span>';
        scrollToBottom();
    }

    function finalizeAnswer(data) {
        const entry = streamingCards[data.id];
        if (!entry) return;

        // Handle error case
        if (data.error) {
            entry.body.innerHTML = `<span style="color: #f85149;">Error: ${escapeHtml(data.error)}</span>`;
            entry.card.style.borderColor = '#f85149';
            delete streamingCards[data.id];
            return;
        }

        // Finalize: remove cursor, update AI label, remove streaming class
        entry.rawText = data.answer || entry.rawText;
        entry.body.innerHTML = formatAnswer(entry.rawText);
        entry.aiLabel.textContent = data.ai || 'gemini';
        entry.card.classList.remove('streaming');

        delete streamingCards[data.id];

        totalAnswers++;
        answerCount.textContent = totalAnswers;
        scrollToBottom();
    }

    // --- Full answer (reconnection / history) ---
    function addAnswer(data) {
        // Hide empty state
        if (emptyState) {
            emptyState.style.display = 'none';
        }

        removeGenerating();

        // Create answer card
        const card = document.createElement('div');
        card.className = 'answer-card';

        const time = new Date(data.timestamp * 1000);
        const timeStr = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const sourceLabel = data.source === 'auto' ? 'AUTO' : data.source === 'screen' ? 'SCREEN' : 'MANUAL';
        const aiLabel = data.ai || 'gemini';

        card.innerHTML = `
            <div class="answer-meta">
                <span class="answer-source">${sourceLabel} · ${aiLabel}</span>
                <span class="answer-time">${timeStr}</span>
            </div>
            <div class="answer-body">${formatAnswer(data.answer)}</div>
        `;

        answersEl.appendChild(card);
        totalAnswers++;
        answerCount.textContent = totalAnswers;
        scrollToBottom();
    }

    function showError(message) {
        const card = document.createElement('div');
        card.className = 'answer-card';
        card.style.borderColor = '#f85149';
        card.innerHTML = `
            <div class="answer-body" style="color: #f85149;">
                Error: ${escapeHtml(message)}
            </div>
        `;
        answersEl.appendChild(card);
        scrollToBottom();
    }

    // --- Formatting ---
    function formatAnswer(text) {
        // Simple markdown-ish formatting
        let html = escapeHtml(text);

        // Bold: **text**
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        // Inline code: `text`
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Code blocks: ```...```
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (_, lang, code) {
            return '<pre><code>' + code.trim() + '</code></pre>';
        });

        // Line breaks
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function scrollToBottom() {
        requestAnimationFrame(function () {
            answersEl.scrollTop = answersEl.scrollHeight;
        });
    }

    // --- Manual Input ---
    async function sendQuestion() {
        const question = manualInput.value.trim();
        if (!question) return;

        manualInput.value = '';

        try {
            const resp = await fetch('/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: question }),
            });

            if (!resp.ok) {
                showError('Failed to send question');
            }
        } catch (e) {
            showError('Connection error');
        }
    }

    // --- Screen Analysis ---
    async function analyzeScreen() {
        if (analyzeBtn.classList.contains('analyzing')) return; // Prevent double-click

        analyzeBtn.classList.add('analyzing');

        try {
            const resp = await fetch('/analyze-screen', {
                method: 'POST',
            });

            if (!resp.ok) {
                const data = await resp.json().catch(() => ({}));
                showError(data.error || 'Screen analysis failed');
            }
        } catch (e) {
            showError('Connection error');
        }

        // Remove analyzing state after a short delay (the SSE answer-done will handle UI)
        setTimeout(() => {
            analyzeBtn.classList.remove('analyzing');
        }, 3000);
    }

    // Enter to send, Ctrl+Enter to analyze screen
    manualInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && e.ctrlKey) {
            e.preventDefault();
            analyzeScreen();
        } else if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendQuestion();
        }
        // Escape to clear
        if (e.key === 'Escape') {
            manualInput.value = '';
            manualInput.blur();
        }
    });

    // Global Ctrl+Enter (works even when input not focused)
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && e.ctrlKey) {
            e.preventDefault();
            analyzeScreen();
        }
    });

    sendBtn.addEventListener('click', sendQuestion);
    analyzeBtn.addEventListener('click', analyzeScreen);

    // --- Click-Through Logic ---
    // Allow clicks to pass through to windows below, except for interactive elements
    const ghostApp = document.getElementById('ghost-app');
    const footer = document.querySelector('footer');
    const buttons = document.querySelectorAll('button');
    const input = document.getElementById('manual-input');

    // Default: pass clicks through to windows below
    ghostApp.style.pointerEvents = 'none';

    // Re-enable pointer events on interactive elements
    footer.style.pointerEvents = 'auto';
    input.style.pointerEvents = 'auto';
    buttons.forEach(btn => {
        btn.style.pointerEvents = 'auto';
    });

    // --- Init ---
    connectSSE();

})();
