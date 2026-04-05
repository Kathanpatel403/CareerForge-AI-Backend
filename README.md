# AI Career Copilot API

This is the backend for the AI Career Copilot. It is built using FastAPI, MongoDB (Motor/Beanie), and LangGraph/LangChain.

## Prerequisites
- Python 3.10+
- MongoDB instance (local or Atlas)
- Required API Keys (OpenAI, etc.)

## Project Structure

```bash
Backend/
├── app/
│   ├── api/          # Route definitions
│   ├── core/         # Core settings, configurations, security
│   ├── db/           # Database connection and config
│   ├── models/       # Beanie/Pydantic models
│   ├── services/     # Business logic (GenAI/LangGraph apps)
│   └── main.py       # FastAPI application initialisation
├── .env              # Environment variable overrides
├── .env.example      # Example environment variables
└── requirements.txt  # Project dependencies
```

## Setup Instructions

1. **Create Virtual Environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Copy `.env.example` to `.env` and fill in your database URI and API keys.
   ```bash
   cp .env.example .env
   ```

4. **Run the Application:**
   ```bash
   uvicorn app.main:app --reload
   ```

5. **API Documentation:**
   Once running, explore the interactive documentation at:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc
