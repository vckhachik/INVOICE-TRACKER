# INVOICE-TRACKER
Central Platform to track all company invoices 
Invoice Tracking Automation

Internal invoice intake and tracking platform for group payables.

⸻

🚀 Overview

This platform centralises invoice management across multiple projects and entities. It automates data extraction, standardises tracking workflows, and provides real-time visibility into operational finance processes.

The system is designed to reduce manual processing, improve accuracy, and create a single source of truth for invoice status and reporting.

⸻

✨ Key Features

📥 Ingestion & Processing
	•	Invoice upload (manual or folder-based ingestion)
	•	OCR-based data extraction (Azure Document Intelligence / AWS Textract)
	•	Automatic entity and project mapping

📊 Tracking & Workflow
	•	Centralised invoice register
	•	Status tracking:
	•	Paid / Unpaid
	•	Approved / Not approved
	•	VAT recovered / Unrecovered
	•	Exception handling via review queue
	•	Manual override for edge cases

📈 Reporting & Visibility
	•	Dashboard views for operational finance tracking
	•	Real-time status monitoring across entities/projects

⸻

🧭 Product Positioning

This tool is designed for invoice tracking and workflow management.

❗ It is not an accounting system or ERP
❗ It does not replace general ledger or financial reporting systems

Instead, it sits upstream of accounting, acting as an operational layer for invoice intake, validation, and tracking.

⸻

🏗️ Architecture Overview
        ┌──────────────────────────┐
        │   Invoice Sources        │
        │ (Uploads / Folders)      │
        └────────────┬─────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │ OCR Processing Layer     │
        │ (Azure / AWS Textract)   │
        └────────────┬─────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │ Backend API (FastAPI)    │
        │ - Validation             │
        │ - Mapping                │
        │ - Business Logic         │
        └────────────┬─────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │ Database (PostgreSQL)    │
        │ - Invoice Register       │
        │ - Status Tracking        │
        └────────────┬─────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │ Frontend (Streamlit)     │
        │ - Dashboard              │
        │ - Review Queue           │
        └──────────────────────────┘
        
        🛠️ Tech Stack
        Layer --> Technology
Backend --> FastAPI
Database --> PostgreSQL
ORM --> SQLAlchemy
Migrations --> Alembic
Frontend --> Streamlit
Infrastructure --> Docker Compose
OCR --> Azure Document Intelligence / AWS Textract

📁 Project Structure
.
├── backend/            # FastAPI application
├── frontend/           # Streamlit dashboard
├── db/                 # Database models & migrations
├── ingestion/          # Invoice ingestion logic
├── services/           # OCR + processing services
├── scripts/            # Seed & utility scripts
├── docker-compose.yml
└── README.md

 Local Development Setup

1. Clone Repository
git clone <repo-url>
cd <repo-name>

2. Environment Setup
cp .env.example .env

3. Start Services
docker-compose up --build

4. Run Migrations
alembic upgrade head

Access Applications
	•	Backend API: http://localhost:8000
	•	Frontend (Streamlit): http://localhost:8501

🔄 Core Workflow
	1.	Upload invoice (or ingest from folder)
	2.	Extract data via OCR
	3.	Map to entity and project
	4.	Store in invoice register
	5.	Assign and update statuses
	6.	Review exceptions (if any)
	7.	Track via dashboard

⸻

🧪 MVP Scope
	•	Invoice ingestion
	•	OCR extraction
	•	Entity/project mapping
	•	Invoice register
	•	Status toggles
	•	Dashboard
	•	Exception review queue

⸻

🛣️ Roadmap

Short Term
	•	Improved duplicate detection
	•	Enhanced authentication & role management
	•	UI/UX improvements

Medium Term
	•	Integration with accounting/finance systems
	•	Audit logs & activity tracking
	•	Bulk processing enhancements

Long Term
	•	AI-based anomaly detection
	•	Smart approval workflows
	•	Predictive cashflow insights

⸻

🔐 Security & Access (Planned)
	•	Role-based access control (RBAC)
	•	Environment-based configuration
	•	Secure handling of invoice data

⸻

🤝 Contributing
Internal project — contributions should follow:
	•	Standard branch naming conventions
	•	PR review process
	•	Clear documentation for new features

⸻

📌 Notes
	•	This is an operational finance tool, not a replacement for accounting systems
	•	Designed to scale across multiple entities and projects
	•	Built for extensibility and integration

⸻

📬 Contact

For questions or contributions, contact the project owner or internal tech team.
:::
