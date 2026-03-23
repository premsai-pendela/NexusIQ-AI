# 🧠 NexusIQ AI
**AI-Powered Business Intelligence Platform | Natural Language → SQL → Insights**

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Google Gemini](https://img.shields.io/badge/Gemini-AI-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![DuckDB](https://img.shields.io/badge/DuckDB-Analytics-FFF000?style=for-the-badge&logo=duckdb&logoColor=black)](https://duckdb.org)

> 🚀 **Ask business questions in plain English → Get SQL insights, charts, and explanations in seconds**

---

## 🔥 Why This Project Matters

Traditional analytics workflow:
- Write SQL → Debug → Export → Visualize → Explain  
⏱️ **Time: 2–3 hours per analysis**

**NexusIQ replaces this with:**
- Ask question → Get answer + chart + explanation  
⚡ **Time: ~3–8 seconds**

---

## 📊 Impact & Results

- ⚡ Query execution: **2–8 seconds**
- 📉 Manual effort reduced: **~95%**
- 📊 Dataset handled: **100,000+ transactions**
- 💰 Revenue analyzed: **$139M**
- 👥 Designed for **non-technical stakeholders**

---

## 🎬 Demo

![NexusIQ Demo](docs/demo.gif)

🔗 **Live Demo:** *(Add your Render/Streamlit link here — this is critical)*  

---

## 🧠 Core Capabilities

### 💬 Natural Language → SQL Engine
- Converts plain English into optimized SQL
- Context-aware multi-turn conversations
- Auto error correction & suggestions

---

### 📊 Interactive Analytics Dashboard
- 6 chart types: Bar, Line, Pie, Scatter, Area, Horizontal
- Custom axes & grouping
- Real-time rendering

---

### 🧠 Smart Query Intelligence
- Typo detection ("wset" → "west")
- Date range validation
- Context understanding
- Follow-up queries supported

---

### 🔒 Enterprise-Grade Safety
- Read-only queries only
- SQL injection protection
- Query timeout control
- Model failover handling

---

### 📥 Export System
- CSV  
- JSON  
- Excel  
- Markdown  

---

## ⚙️ System Architecture

```mermaid
graph LR
    A[User Query] --> B[Gemini 2.0 Flash]
    B --> C{Complexity Detection}
    C -->|Simple| D[Fast Model]
    C -->|Complex| E[Advanced Model]
    D --> F[SQL Query]
    E --> F
    F --> G[DuckDB Engine]
    G --> H[Query Results]
    H --> I[Chat UI]
    I --> J{User Action}
    J -->|Visualize| K[Charts]
    J -->|Export| L[Files]

🧱 Tech Stack
| Layer         | Technology                 |
| ------------- | -------------------------- |
| LLM           | Gemini 2.0 Flash / 1.5 Pro |
| Query Engine  | DuckDB                     |
| Backend       | Python                     |
| Frontend      | Streamlit                  |
| Visualization | Plotly                     |
| Data Handling | Pandas                     |

📦 Setup (Run Locally)
git clone https://github.com/premsai-pendela/NexusIQ-AI.git
cd NexusIQ-AI

python -m venv venv
source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt

cp .env.example .env

Add in .env:

GOOGLE_API_KEY=your_key
DATABASE_PATH=data/sales.db

Run:

python database/generate_data.py
streamlit run app.py
🎯 Example Queries
"What is total revenue?"
"Top 10 customers by revenue"
"Monthly sales trend"
"Compare Q1 vs Q2 performance"
"Best performing product category"
📊 Dataset Overview

100,000 transactions

$139M total revenue

5 regions

5 product categories

2+ years of data

📈 Performance Metrics
Metric	Value
Simple Queries	2–3 sec
Complex Queries	5–8 sec
Chart Rendering	~0.5 sec
Export (10K rows)	~1 sec
🧪 Testing
pytest tests/ -v
pytest --cov=agents tests/
🗺️ Roadmap
✅ Completed

SQL AI Agent

Chat Interface

Visualization Engine

Export System

🚧 In Progress

RAG Document Agent

Web Data Agent

Multi-agent orchestration

🔮 Future

Voice-based analytics

Scheduled reports

Multi-database support

REST API layer

💼 Real-World Use Cases

📊 Sales → Top customers & revenue insights

📈 Marketing → Campaign performance analysis

💰 Finance → Revenue trends & forecasting

🎯 Product → Category performance tracking

🤝 Contributing
git checkout -b feature/your-feature
git commit -m "Add feature"
git push origin feature/your-feature
📝 License

MIT License

👤 Author

Prem Sai Pendela
🔗 GitHub: https://github.com/premsai-pendela

<div align="center">

⭐ If this project impressed you, give it a star

</div> ```