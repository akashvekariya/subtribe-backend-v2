# Subtribe ATS Backend Documentation

> **Status**: ✅ Production Deployed (v1.0.1) | **Framework**: FastAPI | **Deployment**: Google Cloud Run

Multi-tenant SaaS Applicant Tracking System for recruiting companies.

---

## 📚 Documentation

### Core Documentation
- **[Architecture](Architecture)** - System design, tech stack, and key decisions
- **[Database Schema](Database-Schema)** - Tables, relationships, and indexes
- **[API Reference](API-Reference)** - Endpoints, authentication, and error responses
- **[Development Guide](Development)** - Local setup and development patterns
- **[Deployment](Deployment)** - CI/CD pipeline and production configuration

### Additional Resources
- **[Project Status](Project-Status)** - Current phase and completed features
- **[Multi-Tenancy](Multi-Tenancy)** - Row-level isolation strategy

---

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- PostgreSQL (Supabase)
- Google Cloud account (GCS + Cloud Run)

### Local Development
```bash
# Clone and install
git clone <repo-url>
cd subtribe-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.development.example .env
# Edit .env with your credentials

# Run migrations and start
alembic upgrade head
uvicorn app.main:app --reload
```

**Server**: http://localhost:8000  
**API Docs**: http://localhost:8000/docs

---

## 🎯 Features

### Core Functionality
- **Authentication**: Email/password via Supabase Auth with company-scoped JWTs
- **Company Management**: Profile, branding, and settings
- **Job Postings**: Create, publish, and manage job listings
- **Applications**: Public application submission with resume uploads
- **Status Tracking**: Pipeline management with audit history
- **File Storage**: Resume storage on Google Cloud Storage with signed URLs

### Technical Highlights
- **Multi-Tenant**: Row-level isolation via `company_id` filtering
- **Async**: Full async/await implementation with asyncpg
- **Secure**: JWT authentication, private GCS buckets, input validation
- **Scalable**: Cloud Run auto-scaling, connection pooling, optimized queries
- **Production-Ready**: CI/CD pipeline, automated versioning, zero-downtime deploys

---

## 📊 Architecture Overview

**Pattern**: Monolithic REST API  
**Database**: PostgreSQL (Supabase)  
**Storage**: Google Cloud Storage  
**Hosting**: Google Cloud Run  

See [Architecture](Architecture) for detailed design decisions.

---

## 🔗 External Links

- **API Documentation**: https://your-api.run.app/docs
- **Supabase Dashboard**: https://supabase.com/dashboard
- **GCP Console**: https://console.cloud.google.com

---

**Last Updated**: 2025-10-12  
**Version**: v1.0.1  
**License**: Proprietary

