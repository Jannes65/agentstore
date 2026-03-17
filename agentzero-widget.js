document.addEventListener('DOMContentLoaded', function() {
(function() {
    // 1. CSS for the widget
    const style = document.createElement('style');
    style.innerHTML = `
        #az-widget-container {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 99999;
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
            z-index: 99999;
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
        .az-quick-replies {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
        }
        .az-quick-reply {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 16px;
            padding: 6px 12px;
            font-size: 12px;
            color: #8b949e;
            cursor: pointer;
            transition: all 0.2s;
        }
        .az-quick-reply:hover {
            border-color: #f7931a;
            color: #f7931a;
        }
        .az-wizard-card {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 12px;
            margin-top: 8px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .az-wizard-card select, .az-wizard-card input {
            background-color: #0d1117;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 8px;
            color: #c9d1d9;
            font-size: 14px;
        }
        .az-wizard-card button {
            background-color: #f7931a;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 10px;
            font-weight: bold;
            cursor: pointer;
        }
        .az-wizard-card button:disabled {
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
    let wizardState = null; // { step: 1, data: {} }
    const API_BASE = "https://agentstore-production.up.railway.app";
    const path = (window.location && window.location.pathname) ? window.location.pathname : '';
    const currentPage = path.split('/').pop() || 'index.html';

    // 4. Logic Functions
    async function fetchBTCPrice() {
        try {
            const r = await fetch(`${API_BASE}/btc-price`);
            const d = await r.json();
            usdPerSat = d.usd / 100000000;
        } catch(e) { /* keep fallback */ }
    }

    function addMessage(role, content, isHtml = false) {
        const div = document.createElement('div');
        div.className = `az-msg az-msg-${role === 'user' ? 'user' : 'agent'}`;
        if (isHtml) div.innerHTML = content;
        else div.textContent = content;
        transcript.appendChild(div);
        transcript.scrollTop = transcript.scrollHeight;
        return div;
    }

    function showQuickReplies(replies) {
        const container = document.createElement('div');
        container.className = 'az-quick-replies';
        replies.forEach(reply => {
            const btn = document.createElement('div');
            btn.className = 'az-quick-reply';
            btn.textContent = reply.text;
            btn.onclick = () => {
                container.remove();
                if (reply.action) {
                    reply.action();
                } else {
                    input.value = reply.text;
                    handleSend();
                }
            };
            container.appendChild(btn);
        });
        transcript.appendChild(container);
        transcript.scrollTop = transcript.scrollHeight;
    }

    async function showCodeReviewWizard() {
        const builderId = sessionStorage.getItem('builder_id');
        
        if (!builderId) {
            addMessage('agent', 'Please log into your Builder Dashboard first, then try again.');
            return;
        }
        
        // Fetch agents directly from API
        const res = await fetch(`${API_BASE}/builders/${builderId}`);
        const data = await res.json();
        const agents = data.agents || [];
        
        if (agents.length === 0) {
            addMessage('agent', 'No agents found. Please submit an agent first.');
            return;
        }
        
        let agentOptions = agents.map(a => 
            `<button onclick="selectAgentForReview('${a.id}', '${a.name}')" 
             style="display:block;width:100%;margin:4px 0;padding:8px;background:#f7931a;color:white;border:none;border-radius:6px;cursor:pointer">
             ${a.name}
             </button>`
        ).join('');
        
        addMessage('agent', `<div><b>🔒 Code Review — 500 sats</b><br><br>Select the agent to review:<br><br>${agentOptions}</div>`, true);
    }

    // Attach to window so onclick works
    window.selectAgentForReview = function(agentId, agentName) {
        window.reviewAgentId = agentId;
        addMessage('user', agentName);
        addMessage('agent', `Great! Paste your GitHub repository URL for <b>${agentName}</b>:<br>
            <input id="githubUrlInput" type="text" placeholder="https://github.com/..." 
            style="width:100%;padding:8px;margin-top:8px;border-radius:6px;border:1px solid #ccc;background:#161b22;color:#c9d1d9;">
            <button onclick="startCodeReview()" 
            style="width:100%;margin-top:8px;padding:8px;background:#f7931a;color:white;border:none;border-radius:6px;cursor:pointer">
            Pay 500 sats & Review ⚡
            </button>`, true);
    }

    window.startCodeReview = async function() {
        const githubUrl = document.getElementById('githubUrlInput').value;
        const userId = sessionStorage.getItem('user_id') || 'jannes_001';
        
        if (!githubUrl) {
            addMessage('agent', 'Please enter a GitHub URL first.');
            return;
        }
        
        addMessage('user', githubUrl);
        addMessage('agent', '⏳ Processing payment and starting review...');
        
        const res = await fetch(`${API_BASE}/agents/review`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                github_url: githubUrl,
                agent_id: window.reviewAgentId,
                user_id: userId
            })
        });
        const data = await res.json();
        
        if (data.status === 'payment_required') {
            addMessage('agent', `❌ Insufficient balance. You need 500 sats. Please deposit first.`);
            return;
        }
        
        addMessage('agent', `✅ <b>Review Complete!</b><br><br>${data.review_report}<br><br>${data.badge_awarded ? '🏆 Verified badge awarded!' : '🔍 Reviewed badge added.'}`, true);
    }

    async function handleSend() {
        const text = input.value.trim();
        if (!text) return;

        if (text.toLowerCase().includes("code review") || text.toLowerCase().includes("review") || text.toLowerCase().includes("verified badge")) {
             addMessage('user', text);
             input.value = '';
             showCodeReviewWizard();
             return;
        }

        addMessage('user', text);
        input.value = '';
        sendBtn.disabled = true;

        messages.push({ role: 'user', content: text });

        const systemPrompt = `You are AgentZero, the AI assistant for AgentStore — the Bitcoin Lightning-native AI agent marketplace at chooseyouragents.com. 

Current BTC context: 1 sat is approximately $${usdPerSat.toFixed(8)}.

You help two types of users:
1. BUILDERS listing agents — help them write clear descriptions, define permissions, set fair prices in sats, and explain what makes a good agent listing. Offer a premium assisted listing service for 500 sats (~$${(500 * usdPerSat).toFixed(2)}).
2. BUYERS looking for agents — ask what they need, recommend agents from the marketplace, explain what each agent does, and suggest agent combinations for complex tasks.

When a user asks about code review, security audit, or verified badge:
1. Ask for their Agent ID and GitHub URL (or offer direct paste)
2. Explain the cost: 500 sats (~$X USD)
3. Tell them to deposit sats first if needed
4. Once they provide the details, respond with exactly this JSON format:
{"action": "code_review", "agent_id": "xxx", "github_url": "xxx", "user_id": "xxx"}

Always mention sats prices with USD equivalent. 
When helping builders, offer the AgentZero Verified Code Review for 500 sats (~$${(500 * usdPerSat).toFixed(2)}) which earns their agent a security badge.
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

            if (message.includes('"action": "code_review"')) {
                try {
                    const reviewData = JSON.parse(message.substring(message.indexOf('{'), message.lastIndexOf('}') + 1));
                    const userId = reviewData.user_id || 'anonymous';
                    
                    // Check balance first
                    const balRes = await fetch(`${API_BASE}/payments/balance/${userId}`);
                    const bal = await balRes.json();
                    if (bal.balance_sats < 500) {
                        addMessage('agent', `You need 500 sats for a code review. Your balance: ${bal.balance_sats} sats. Please top up first.`);
                        return;
                    }
                    
                    addMessage('agent', "Initiating security review...");

                    // Call review endpoint
                    const reviewRes = await fetch(`${API_BASE}/agents/review`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(reviewData)
                    });
                    const review = await reviewRes.json();
                    addMessage('agent', `📋 **Security Review Complete**\n\n${review.review_report}\n\n${review.badge_awarded ? '✅ Verified badge awarded to your agent!' : '🔍 Reviewed badge awarded.'}`);
                } catch (e) {
                    console.error("Failed to parse code review JSON", e);
                    addMessage('agent', message);
                }
            } else {
                addMessage('agent', message);
            }
            messages.push({ role: 'assistant', content: message });
        } catch (error) {
            addMessage('agent', "Sorry, I'm having trouble connecting to my brain. Please try again later!");
        } finally {
            sendBtn.disabled = false;
        }
    }

    // 5. Event Listeners
    document.getElementById('az-bubble').addEventListener('click', function() {
        document.getElementById('az-window').style.display = 'flex';
        document.getElementById('az-bubble').style.display = 'none';
        
        if (messages.length === 0) {
            let greeting = "👋 Hey! I'm AgentZero — your guide to the agent economy. Here's what I can do:\n\n🔍 Help you find the right agent for your needs\n📝 Help you write a perfect agent listing\n🔒 Review your agent's code for security issues (500 sats)\n💡 Suggest agent combinations for complex tasks\n💰 Help you price your agent competitively\n⚡ Explain how Lightning payments work on AgentStore\n\nWhat would you like help with today?";
            if (currentPage === 'builder.html' || currentPage === 'submit.html') {
                greeting = "👋 Listing an agent? I can help you write a great description, set the right price, and get your agent **Verified** with a security review (500 sats). What would you like help with?";
            } else if (currentPage === 'dashboard.html' || (window.agentZeroContext && window.agentZeroContext.page === 'dashboard')) {
                greeting = "👋 Welcome to your dashboard! I can help you manage your agents or start a **Security Review** (500 sats) to get the Verified badge.";
                addMessage('agent', greeting);
                messages.push({ role: 'assistant', content: greeting });
                showQuickReplies([
                    { text: "🔒 Start Code Review", action: showCodeReviewWizard },
                    { text: "💡 Tips for my agents" },
                    { text: "💰 Withdrawal help" }
                ]);
                return;
            }
            addMessage('agent', greeting);
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
});
