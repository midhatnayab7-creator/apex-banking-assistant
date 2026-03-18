# Apex Banking AI Assistant

An intelligent banking assistant powered by **Llama 4 + Groq**, built with Python and deployed on Vercel.

## Live Links

- **Live App**: [https://apex-banking-assistant.vercel.app](https://apex-banking-assistant.vercel.app)
- **Portfolio Showcase**: [https://apex-banking-assistant.vercel.app/showcase.html](https://apex-banking-assistant.vercel.app/showcase.html)

## Features

- **Account Balance** — Check account balances and status
- **Transaction History** — View recent transactions
- **Loan Eligibility** — Check eligibility for personal, home, auto, and business loans
- **Card Security** — Report and block lost/stolen cards instantly
- **Branch Locator** — Find nearest branches and ATMs by city

## Tech Stack

- **AI Model**: Llama 4 Scout (via Groq API)
- **Backend**: Python (Vercel Serverless Functions)
- **Frontend**: Vanilla HTML/CSS/JS
- **Deployment**: Vercel

## How It Works

1. User sends a message through the chat interface
2. Message is sent to a Vercel serverless function (`/api/chat`)
3. The function calls Groq API with Llama 4 + banking tools
4. AI decides which tool to use (account lookup, transactions, loans, card block, branch finder)
5. Tool result is fed back to the AI, which generates a human-friendly response

## Developer

**Midhat Nayab** — [GitHub](https://github.com/midhatnayab7-creator)
