# IFB Materials App - Backend

This is the backend service for the IFB Materials Inventory OS. It powers the frontend by managing data ingestion, providing robust APIs for material queries, analytics, and ensuring data integrity.

## 🚀 Tech Stack

*   **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
*   **Database**: PostgreSQL
*   **ORM**: SQLAlchemy & Psycopg2
*   **Data Processing**: Pandas (for rapid Excel ingestion and cleaning)
*   **Server**: Uvicorn

## 💻 Key Features

*   **Automated Schema Management**: Using SQLAlchemy and custom DB initialization, the app will automatically create required tables and indexes upon starting if they don't exist.
*   **FastAPI Routers**: Clean, modular API routes handling specific domains (Dashboard, Inventory, Analytics, Admin).
*   **Pagination & Filtering**: Efficient data querying through SQLAlchemy, providing paginated responses to handle thousands of material records smoothly.
*   **Bulk Excel Upload**: Dedicated endpoint to ingest `procurement-data.xlsx` via Pandas, parsing monthly trends and static data, then replacing existing DB records cleanly.

## 🛠️ Getting Started

### Prerequisites
*   Python 3.10+
*   PostgreSQL running locally or hosted

### Installation & Setup

1.  Navigate into the backend directory:
    ```bash
    cd materials-backend
    ```

2.  Create and activate a virtual environment:
    ```bash
    python -m venv venv
    
    # On Windows:
    venv\Scripts\activate
    # On Mac/Linux:
    source venv/bin/activate
    ```

3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4.  Configure the Database Connection:
    Copy `.env.example` to `.env` and fill in your PostgreSQL URL.
    ```bash
    cp .env.example .env
    # Example: DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/materials_db
    ```

5.  Run the server:
    ```bash
    uvicorn app.main:app --reload
    ```

6.  Explore the interactive API documentation (Swagger UI) at [http://localhost:8000/docs](http://localhost:8000/docs).

## 📂 Project Structure

```text
materials-backend/
├── app/
│   ├── api/                   # Shared API logic and dependencies (like get_db)
│   ├── core/                  # Database connection config and init_db scripts
│   ├── crud/                  # SQL Query execution and core database operations
│   ├── models/                # SQLAlchemy Table definitions
│   ├── routers/               # API endpoint definitions 
│   ├── schemas/               # Pydantic validation models
│   └── main.py                # FastAPI Application entry point (and lifespan events)
├── data-import.py             # Standalone script for importing data directly
├── .env.example               # Example environment variables
└── requirements.txt           # Python dependencies
```
