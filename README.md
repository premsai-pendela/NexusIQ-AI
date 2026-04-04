# 🧠 NexusIQ AI  
**Multi-Agent AI Business Intelligence Platform | From Questions → Insights → Decisions**

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Google Gemini](https://img.shields.io/badge/Gemini-AI-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![DuckDB](https://img.shields.io/badge/DuckDB-Analytics-FFF000?style=for-the-badge&logo=duckdb&logoColor=black)](https://duckdb.org)

> 🚀 Ask a business question → Multiple AI agents collaborate → Get insights, charts, and decisions in seconds

---

## 🔥 Why This Project Matters

Traditional analytics is fragmented:
- SQL for structured data  
- Documents for context  
- Web for external signals  
- Analysts to interpret everything  

⏱️ **Time: Hours to days**

---

### ⚡ NexusIQ Approach

Instead of one tool, NexusIQ uses a **multi-agent system**:

- Each agent specializes in one task  
- Agents collaborate like a real analytics team  
- Final output is not just data → but **decision-ready insights**

---

## 🧠 Multi-Agent Architecture (Core Idea)

```text
User Question (plain English)
        ↓
    🧠 PLANNER AGENT
    Breaks problem into sub-tasks
        ↓
    ┌────────┬────────┬────────┬────────┬────────┐
    ↓        ↓        ↓        ↓        ↓
  🗄️ SQL   📄 RAG   🌐 WEB   📊 DATA   ⭐ SENTIMENT
  Agent    Agent     Agent     Agent     Agent
    │        │        │        │        │
    └────────┴────────┴────────┴────────┘
                    ↓
            🔗 FUSION AGENT
            Combines all findings
                    ↓
            📈 ANALYST AGENT
            Finds patterns & root causes
                    ↓
            📝 STORYTELLER AGENT
            Generates business insights
                    ↓
                ✅ OUTPUT
```

---

## 🎯 Final Output Includes

- 📊 Interactive charts  
- 🧠 Plain English insights  
- 📄 Source-backed reasoning  
- 📉 Trends & root causes  
- ⭐ Confidence scores  
- 📥 Downloadable reports  

---

## ⚙️ Current Implementation Status

### ✅ Built (Working)
- SQL AI Agent (NL → SQL → Charts)
- Chat-based interface
- Visualization engine
- Export system

### 🚧 In Progress
- Planner Agent
- RAG (document intelligence)
- Multi-agent orchestration
- Fusion & Analyst agents

### 🔮 Planned
- Web intelligence agent
- Sentiment analysis agent
- PDF report generation
- Voice-based analytics

---

## 🧠 Core Capabilities (Current)

### 💬 Natural Language → SQL Engine
- Converts plain English into SQL queries  
- Handles follow-up questions  
- Auto-corrects errors  

---

### 📊 Interactive Dashboard
- Multiple chart types  
- Real-time rendering  
- User-controlled visualizations  

---

### 🔒 Safe Query Execution
- Read-only queries  
- SQL injection protection  
- Timeout handling  

---

### 📥 Export System
- CSV  
- JSON  
- Excel  
- Markdown  

---

## 📊 Dataset Overview

- 100,000+ transactions  
- $139M revenue analyzed  
- 5 regions  
- 5 product categories  
- 2+ years of data  

---

## 📈 Performance (SQL Agent)

| Metric               | Value     |
|---------------------|----------|
| Query Response      | 2–8 sec  |
| Chart Rendering     | ~0.5 sec |
| Export (10K rows)   | ~1 sec   |

---

## 🎬 Demo

🚧 **Coming Soon — Live Demo will be available shortly**

---

## 🧱 Tech Stack

| Layer            | Technology                     |
|------------------|-------------------------------|
| LLM              | Gemini 2.0 Flash / 1.5 Pro    |
| Query Engine     | DuckDB                        |
| Backend          | Python                        |
| Frontend         | Streamlit                     |
| Visualization    | Plotly                        |
| Data Handling    | Pandas                        |

---

## 📦 Setup (Run Locally)

```bash
git clone https://github.com/premsai-pendela/NexusIQ-AI.git
cd NexusIQ-AI

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
```

<<<<<<< Updated upstream
Run the application:
=======
Add in `.env`:

```env
GOOGLE_API_KEY=your_key
DATABASE_PATH=data/sales.db
```

Run:
>>>>>>> Stashed changes

```bash
python database/generate_data.py
streamlit run app.py
```

---

## 🎯 Example Queries

- What is total revenue?
- Top customers by revenue
- Monthly sales trend
- Compare Q1 vs Q2 performance
- Best performing product category

---

## 💼 Real-World Use Cases

- 📊 Sales → Revenue insights  
- 📈 Marketing → Campaign analysis  
- 💰 Finance → Forecasting  
- 🎯 Product → Performance tracking  

---

## 🤝 Contributing

```bash
git checkout -b feature/your-feature
git commit -m "Add feature"
git push origin feature/your-feature
```

---

## 👤 Author

**Prem Sai Pendela**  
🔗 GitHub: https://github.com/premsai-pendela