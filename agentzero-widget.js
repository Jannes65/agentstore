(function() {
    // 1. CSS for the widget
    const style = document.createElement('style');
    style.innerHTML = `
        #az-widget-container {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 10000;
            font-family: 'DM Sans', sans-serif;
        }
        #az-bubble {
            width: 60px;
            height: 60px;
            background-color: #f7931a;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 30px;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            user-select: none;
        }
        #az-bubble:hover {
            transform: scale(1.1);
        }
        #az-bubble.pulse {
            animation: az-pulse 1.5s ease-in-out;
        }
        @keyframes az-pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.2); box-shadow: 0 0 20px #f7931a; }
            100% { transform: scale(1); }
        }
        #az-window {
            position: absolute;
            bottom: 80px;
            right: 0;
            width: 350px;
            height: 500px;
            background-color: #0d1117;
            border: 1px solid #30363d;
            border-radius: 12px;
            display: none;
            flex-direction: column;
            box-shadow: 0 8px 24px rgba(0,0,0,0.5);
            overflow: hidden;
        }
        #az-header {
            background-color: #161b22;
            padding: 12px 16px;
            border-bottom: 1px solid #30363d;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        #az-header h3 {
            margin: 0;
            font-size: 16px;
            color: #f7931a;
            font-family: 'Syne', sans-serif;
        }
        #az-close {
            cursor: pointer;
            color: #8b949e;
            font-size: 20px;
            line-height: 1;
        }
        #az-transcript {
            flex-grow: 1;
            padding: 16px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .az-msg {
            max-width: 85%;
            padding: 8px 12px;
            border-radius: 12px;
            font-size: 14px;
            line-height: 1.4;
        }
        .az-msg-user {
            align-self: flex-end;
            background-color: #f7931a;
            color: white;
            border-bottom-right-radius: 2px;
        }
        .az-msg-agent {
            align-self: flex-start;
            background-color: #30363d;
            color: #c9d1d9;
            border-bottom-left-radius: 2px;
        }
        #az-input-area {
            padding: 12px;
            border-top: 1px solid #30363d;
            display: flex;
            gap: 8px;
        }
        #az-input {
            flex-grow: 1;
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 8px 12px;
            color: #c9d1d9;
            font-size: 14px;
            outline: none;
        }
        #az-input:focus {
            border-color: #f7931a;
        }
        #az-send {
            background-color: #f7931a;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 12px;
            cursor: pointer;
            font-weight: 600;
        }
        #az-send:disabled {
            background-color: #30363d;
            cursor: not-allowed;
        }
    `;
    document.head.appendChild(style);

    // 2. HTML Structure
    const container = document.createElement('div');
    container.id = 'az-widget-container';
    container.innerHTML = `
        <div id="az-window">
            <div id="az-header">
                <h3>AgentZero — Assistant</h3>
                <span id="az-close">&times;</span>
            </div>
            <div id="az-transcript"></div>
            <div id="az-input-area">
                <input type="text" id="az-input" placeholder="Type a message..." autocomplete="off">
                <button id="az-send">Send</button>
            </div>
        </div>
        <div id="az-bubble">🤖</div>
    `;
    document.body.appendChild(container);

    // 3. Variables & State
    const bubble = document.getElementById('az-bubble');
    const window = document.getElementById('az-window');
    const closeBtn = document.getElementById('az-close');
    const transcript = document.getElementById('az-transcript');
    const input = document.getElementById('az-input');
    const sendBtn = document.getElementById('az-send');
    
    let messages = [];
    let usdPerSat = 0.00075; // fallback
    const API_BASE = "https://agentstore-production.up.railway.app";
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';

    // 4. Logic Functions
    async function fetchBTCPrice() {
        try {
            const r = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd');
            const d = await r.json();
            usdPerSat = d.bitcoin.usd / 100000000;
        } catch(e) { /* keep fallback */ }
    }

    function appendMessage(role, content) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `az-msg az-msg-${role === 'user' ? 'user' : 'agent'}`;
        msgDiv.textContent = content;
        transcript.appendChild(msgDiv);
        transcript.scrollTop = transcript.scrollHeight;
    }

    async function handleSend() {
        const text = input.value.trim();
        if (!text) return;

        appendMessage('user', text);
        input.value = '';
        sendBtn.disabled = true;

        messages.push({ role: 'user', content: text });

        const systemPrompt = `You are AgentZero, the AI assistant for AgentStore — the Bitcoin Lightning-native AI agent marketplace at chooseyouragents.com. 

Current BTC context: 1 sat is approximately $${usdPerSat.toFixed(8)}.

You help two types of users:
1. BUILDERS listing agents — help them write clear descriptions, define permissions, set fair prices in sats, and explain what makes a good agent listing. Offer a premium assisted listing service for 20,000 sats (~$${(20000 * usdPerSat).toFixed(2)}).
2. BUYERS looking for agents — ask what they need, recommend agents from the marketplace, explain what each agent does, and suggest agent combinations for complex tasks.

Always mention sats prices with USD equivalent. 
When helping builders, offer the AgentZero Verified Code Review for 20,000 sats (~$${(20000 * usdPerSat).toFixed(2)}) which earns their agent a security badge.
Be concise, friendly, and Bitcoin-native in tone.`;

        try {
            const response = await fetch(`${API_BASE}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: 'claude-sonnet-4-20250514',
                    system: systemPrompt,
                    messages: messages,
                    max_tokens: 1024
                })
            });

            if (!response.ok) throw new Error('Failed to fetch');
            const data = await response.json();
            const message = data.content[0].text;
            
            appendMessage('agent', message);
            messages.push({ role: 'assistant', content: message });
        } catch (error) {
            appendMessage('agent', "Sorry, I'm having trouble connecting to my brain. Please try again later!");
        } finally {
            sendBtn.disabled = false;
        }
    }

    // 5. Event Listeners
    document.getElementById('az-bubble').addEventListener('click', function() {
        document.getElementById('az-window').style.display = 'flex';
        document.getElementById('az-bubble').style.display = 'none';
        
        if (messages.length === 0) {
            let greeting = "👋 Looking for an agent? Tell me what you need and I'll find the best match.";
            if (currentPage === 'builder.html' || currentPage === 'submit.html') {
                greeting = "👋 Listing an agent? I can help you write a great description and set the right price.";
            } else if (currentPage === 'dashboard.html') {
                greeting = "👋 Want to boost your agent's visibility? I can review your listing and offer tips.";
            }
            appendMessage('agent', greeting);
            messages.push({ role: 'assistant', content: greeting });
        }
    });

    document.getElementById('az-close').addEventListener('click', function() {
        document.getElementById('az-window').style.display = 'none';
        document.getElementById('az-bubble').style.display = 'flex';
    });

    sendBtn.onclick = handleSend;
    input.onkeypress = (e) => { if (e.key === 'Enter') handleSend(); };

    // 6. Init
    fetchBTCPrice();
    setTimeout(() => {
        bubble.classList.add('pulse');
    }, 10000);
})();
