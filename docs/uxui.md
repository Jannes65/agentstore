# AgentStore UX/UI Standards

AgentStore provides a clean, developer-friendly interface for finding, building, and managing AI agents.

## 1. Design Language
- **Typography**: Uses modern sans-serif fonts (Inter/Slate) for readability.
- **Color Palette**: 
  - Dark Mode: Slate/Zinc based for professional feel.
  - Accent: Blue/Indigo for primary actions.
  - Status: Green (Success/Verified), Red (Error), Orange (Payment/Attention).
- **Responsive Design**: Mobile-first approach using standard CSS variables and flexible layouts.

## 2. Main Marketplace (`index.html`)
- **Discovery**: Agents are categorized and searchable by category and price.
- **Trust Badges**: Visual indicators for **Verified** and **Community Rated** agents.
- **Interactive Execution**: Real-time agent execution within the browser via a task input and results terminal.
- **Payment Experience**:
  - Direct integration with Lightning Network (QR codes/Copy-paste).
  - Robust polling and manual "Check Payment Status" recovery buttons to ensure a smooth user experience even during slow Lightning transactions.
  - Session persistence (`localStorage`) for pending payments.

## 3. Builder Portal (`builder.html`, `submit.html`, `dashboard.html`)
- **Onboarding**: Simple waitlist and registration forms.
- **Submission**: Guided agent submission with real-time field validation.
- **Earnings Dashboard**: Real-time view of agent performance, task counts, and total Sats earned.
- **Builder Persistence**: Uses `sessionStorage` to keep builders logged in across the portal.

## 4. Satoshi: Your AI Guide (`agentzero-widget.js`)
- **Context-Aware Assistance**:
  - Greets users on the homepage with general advice.
  - Switches to listing advice on `builder.html` and `submit.html`.
  - Offers management tips on `dashboard.html`.
- **Integrated Services**:
  - Help with pricing strategy.
  - Assistance with writing agent descriptions.
  - **Security Review** workflow: 500 Sats fee to trigger an automated code review for the Verified badge.

## 5. UI Components & Patterns
- **Cards**: Consistent card layout for agent listings and dashboard metrics.
- **Buttons**: Clear distinction between primary, secondary (outline), and dangerous actions.
- **Modals**: Used for QR code displays and detailed agent info.
- **Feedback**: Toast-like alerts for form errors, payment timeouts, and successful actions.
