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

    let eventSource = null;
    let totalAnswers = 0;
    let generatingEl = null;

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
                addAnswer(data);
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

        // Show/remove generating indicator
        if (state === 'generating') {
            showGenerating();
        } else {
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
        const sourceLabel = data.source === 'auto' ? 'AUTO' : 'MANUAL';
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

    // Enter to send
    manualInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendQuestion();
        }
        // Escape to clear
        if (e.key === 'Escape') {
            manualInput.value = '';
            manualInput.blur();
        }
    });

    sendBtn.addEventListener('click', sendQuestion);

    // --- Init ---
    connectSSE();

})();
