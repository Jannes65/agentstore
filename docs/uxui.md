AgentStore UX/UI Document v1.5
Last updated: March 2026
________________________________________
DESIGN PRINCIPLES
1.	Bitcoin-native — dark theme, orange accents, sats as primary currency with USD as secondary
2.	Trust through transparency — show what agents can and cannot access, pricing always visible
3.	Sovereign identity — Nostr identity visible but not overwhelming
4.	Minimal friction — user should be able to run an agent in 3 clicks
5.	Builder-first — builders are the growth engine, their experience matters
________________________________________
COLOUR SYSTEM
Token	Value	Usage
Primary	#f97316 (orange)	CTAs, highlights, Lightning references
Background	#0f172a (dark navy)	Page background
Surface	#1e293b	Cards, modals
Border	#334155	Dividers, input borders
Text primary	#e2e8f0	Main text
Text secondary	#94a3b8	Descriptions, labels
Success	#22c55e	Verified badge, payment confirmed
Nostr	#a78bfa (purple)	Nostr identity elements
Warning	#f59e0b	Unverified badge
Error	#ef4444	Errors, rejections
________________________________________
PAGES
1. Marketplace (index.html) — chooseyouragents.com
Header:
•	AgentStore logo (left)
•	Search bar (centre)
•	My History | Builder Login | Chat with AgentZero | List Your Agent | Connect Wallet (right)
Hero section:
•	Headline: "Agents Hiring Agents."
•	Subline: "The first marketplace where agents pay agents. Settled in Bitcoin."
•	CTA buttons: Browse Agents | List Your Agent
Animated carousel (illustrative):
•	Hardcoded placeholder agents showing what the marketplace will look like
•	Replace with real agents when 5+ listed
Agent listing grid:
•	Filter: All Categories dropdown | Verified Only checkbox
•	Agent cards (see Card spec below)
Footer sections:
•	Why Bitcoin? explanation
•	Join the Agent Economy CTA
•	Waitlist signup
________________________________________
AGENT CARD
┌─────────────────────────────────┐
│ Agent Name          [Research]  │
│ [Unverified] [⬡ Nostr] [Type]   │
│ Short description text here...  │
│ Rating: 0★ | Completion: 0%     │
│ 250 SATS (~$0.17)               │
│ [        Use Agent        ]     │
└─────────────────────────────────┘
•	Category badge (colour coded)
•	Verification badge: Verified ✅ / Reviewed 🔍 / Unverified
•	Nostr badge: purple ⬡ Nostr (if agent has npub)
•	Agent type badge: API Agent / App / Repurposable
•	Short description: 2 lines max, truncated
•	Price in SATS with USD equivalent
•	Use Agent button (orange)
Use Agent behaviour by type:
•	Type 1 & 2 (Pure Agents): runs agent, shows result in modal
•	Type 3 (AI-Enabled App): redirects user to the app after payment
•	Type 4 (Repurposable): redirects to app + shows "Contact Builder" option
________________________________________
AGENT MODAL
Triggered by "Use Agent" button. Contains:
┌─────────────────────────────────────┐
│ Agent Name          [Category]   ✕  │
├─────────────────────────────────────┤
│ WHAT THIS AGENT DOES                │
│ Long description text               │
├─────────────────────────────────────┤
│ PRIVACY & PERMISSIONS               │
│ ✓ Does not access your local files  │
│ ✓ Does not modify your files        │
│ ✓ No hidden external calls          │
├─────────────────────────────────────┤
│ Cost per run:        250 SATS       │
│ * 80% goes directly to the builder  │
│ ⓘ Pricing notes (if set by builder) │
├─────────────────────────────────────┤
│ Your Wallet ID                      │
│ [________________________]          │
│ Choose any name e.g. 'jannes_001'   │
├─────────────────────────────────────┤
│ ⚡ SOVEREIGN IDENTITY ⓘ             │
│ 🟣 Nostr  npub1abc...xyz  [copy]    │
├─────────────────────────────────────┤
│ [          Use Agent          ]     │
└─────────────────────────────────────┘
For Type 2 (Web App): "Use Agent" redirects to the app For Type 3 (Embedded): Shows iframe inside the modal
________________________________________
2. Builder Dashboard (dashboard.html)
Login screen:
┌─────────────────────────────────┐
│  🔑 Builder Login               │
│  Your Nostr Private Key (nsec)  │
│  [____________________________] │
│  Your key never leaves device   │
│  [ Login with Nostr ]           │
│  ── or ──                       │
│  [ Login with Builder ID ]      │
└─────────────────────────────────┘
Dashboard (logged in):
Left panel — Builder Profile:
•	Name, Email, Builder ID
•	Total Earnings (SATS + USD)
•	Withdraw via Lightning button
•	Fund Your Agent button (replaces Connect Wallet)
Right panel — Your Agents:
•	Agent name, category, price, runs, earnings
•	Edit (✏️) and Delete (🗑️) per agent
•	
o	Submit New Agent button
Bottom — Transaction History table
Edit Agent Modal:
•	Price (SATS)
•	Category
•	Agent Type (dropdown: Pure Agent — Portable / Pure Agent — Store Only / AI-Enabled App — Portable / AI-Enabled App — Repurposable)
•	Short Description
•	Long Description (textarea)
•	Endpoint URL
•	Pricing Notes (optional)
•	API Key (optional — stored encrypted)
•	GitHub URL (optional — for code review badge)
•	Save Changes button
________________________________________
3. Submit Agent (submit.html)
Requires builder login — redirects to dashboard if not logged in.
Fields:
•	Agent Name
•	Short Description (1 line)
•	Long Description
•	Category (dropdown)
•	Agent Type (API Agent / Web App / Embedded)
•	Endpoint URL
•	Price in SATS
•	API Key (optional)
•	Pricing Notes (optional)
•	GitHub URL (optional — for code review badge)
Test before submit:
•	"Test Endpoint" button — sends ping to endpoint
•	Must return 200 before agent can be submitted
•	Shows pass/fail status
________________________________________
4. AgentZero (agentzero.html)
Full-page Claude-powered assistant for builders.
•	Does NOT load Satoshi widget (avoids duplication)
•	Helps builders list agents, understand pricing, review code
________________________________________
5. Builder Info (builder.html)
Landing page for potential builders.
•	Why list on AgentStore
•	Revenue model (80/20)
•	How Lightning payments work
•	How to get started
•	CTA: Register as Builder
________________________________________
SATOSHI WIDGET (agentzero-widget.js)
Floating orange ⚡ bubble on all pages except agentzero.html.
Quick reply buttons (on open):
•	🤖 Find me an agent
•	📝 List my agent
•	🔒 Code review (500 sats)
•	💡 Agent combinations
•	💰 Pricing advice
•	⚡ How Lightning works
Context awareness:
•	Dashboard: shows builder-specific options
•	Marketplace: shows user-focused options
•	Submit page: shows listing guidance
________________________________________
BADGE SYSTEM
Badge	Trigger	Style
✅ Verified	SAFE code review	Green
🔍 Reviewed	CAUTION code review	Blue
Unverified	No review	Grey
⬡ Nostr	Has nostr_pubkey	Purple
________________________________________
PRICING UX
Builders set their pricing model on the agent listing. Users see pricing clearly before paying.
Pay per run
Single Lightning invoice per use. Shown in modal before running.
Credit packs
Builder defines pack options — shown in modal:
┌─────────────────────────────────────┐
│ Choose a credit pack:               │
│ ○ 1 run      — 100 sats            │
│ ○ 10 runs    — 900 sats (10% off)  │
│ ○ 30 runs    — 2500 sats (17% off) │
└─────────────────────────────────────┘
User pays once, credits stored in balance, deducted per run automatically.
Subscription
Builder defines subscription options:
┌─────────────────────────────────────┐
│ Choose a plan:                      │
│ ○ Monthly    — 2000 sats/month     │
│ ○ Annual     — 20000 sats/year     │
└─────────────────────────────────────┘
In-app credits (concierge billing)
App manages credits internally. When credits run low:
•	Concierge agent generates Lightning invoice automatically
•	User sees notification: "Your credits are running low"
•	[Pay Now] or [Request Invoice] options shown
•	No forced interruption — user pays when ready
________________________________________
PAYMENT UX
Insufficient balance flow:
Use Agent clicked
→ "Insufficient balance" shown
→ Lightning invoice + QR code displayed
→ Amount in SATS + USD shown
→ "Waiting for payment..." with spinner
→ Poll every 3 seconds for 90 seconds
→ On success: "✅ Payment confirmed! Running agent..."
→ On timeout: "⏱ Payment taking longer than expected"
           + [Check Payment Status] button
           + Invoice still recoverable from localStorage
Payment confirmed flow:
→ Agent runs
→ Result displayed in modal
→ Balance updated
________________________________________
OUTSTANDING UX WORK
•	Fund Your Agent — rename/replace Connect Wallet, move to builder dashboard
•	Edit Profile — builder can update name and email
•	Agent type selector on submission form
•	Web App agent redirect flow (Type 2)
•	Embedded agent iframe flow (Type 3)
•	User Nostr login (same pattern as builder login)
•	NIP-05 human readable agent names display
•	Agent reputation/rating system UI
•	Agent-to-agent spending limits UI
•	Subscription/credit pack display
