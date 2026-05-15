# ✈️ Travel Orchestrator: AI-Powered Frontend

This is the Streamlit-based frontend for the **AI Travel Orchestrator**. It provides a premium, glassmorphic UI for interacting with a multi-agent travel swarm.

## 🌟 Features
- **Dynamic City Tabs**: View hotels and experiences grouped by city stop.
- **AI Package Display**: Beautifully rendered city cards with AI-generated summaries.
- **Interactive Chat**: Refine your trip in real-time using natural language.
- **Sequential Itinerary**: View your final plan as an expandable day-by-day itinerary.
- **Session Persistence**: Switch between different travel planning sessions without losing progress.

## 🚀 Getting Started

### 1. Installation
```bash
cd frontend
pip install -r requirements.txt
```

### 2. Environment Setup
Create a `.env` file or set an environment variable:
```env
BACKEND_URL=https://your-backend-azure-link.azurewebsites.net
```

### 3. Run Locally
```bash
streamlit run app.py
```

## ☁️ Deployment
This app is ready for **Streamlit Cloud** or **Azure App Service**.
1. Push this folder to a GitHub repository.
2. Connect the repo to your hosting provider.
3. Add the `BACKEND_URL` to the **Secrets** or **Environment Variables** section.
