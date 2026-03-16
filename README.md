# 🧠 NexusIQ AI

**Multi-Source Business Intelligence Agent System**

> *Ask any business question in plain English. NexusIQ autonomously investigates across SQL databases, PDF documents, live websites, CSV files, and sentiment data to deliver comprehensive answers with executive summaries.*

## 🎯 The Problem

Business analysts spend 2-3 days manually:
- Querying databases
- Reading through reports
- Scraping competitor data
- Analyzing customer sentiment
- Synthesizing everything into insights

**NexusIQ does this in 2-3 minutes.**

## 🏗️ Architecture
User Question → Planner Agent → [SQL, RAG, Web, Data Agents]
→ Fusion Agent
→ Analyst Agent
→ Answer + Visualizations + PDF

## 🔧 Tech Stack

- **Agent Framework:** LangGraph
- **LLM:** Google Gemini 1.5 Flash (free tier)
- **Database:** PostgreSQL
- **Vector Store:** ChromaDB
- **Frontend:** Streamlit
- **Deployment:** Streamlit Cloud

## 🚀 Quick Start

```bash
# Clone repo
git clone https://github.com/premsai-pendela/NexusIQ-AI.git
cd NexusIQ-AI

# Setup environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure .env with your API keys
cp .env.example .env
# Edit .env with your keys

# Initialize database
python database/setup.py
python database/generate_data.py

# Run app
streamlit run main.py
📊 Features (In Progress)
 SQL Query Agent
 RAG Document Agent
 Web Scraping Agent
 Data Analysis Agent
 Agent Orchestration (LangGraph)
 Streamlit UI
 PDF Report Generation

This project demonstrates autonomous multi-agent systems, RAG implementation, and production-grade AI engineering.
