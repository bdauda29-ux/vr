# NIS Personnel Information Management System

A Flask-based application for managing staff records, leaves, and office assignments within the Nigeria Immigration Service (NIS).

## Features

- **Staff Management**: Add, update, delete, and view staff details.
- **Office Management**: Manage directorate offices.
- **Leave Management**: Track staff leave applications.
- **Exports**: Generate Excel and PDF reports with custom styling and zebra striping.
- **Dashboard**: Visual statistics of staff distribution.
- **Authentication**: Role-based access control.

## Tech Stack

- **Backend**: Python (Flask), SQLAlchemy
- **Frontend**: HTML, Bootstrap 5, JavaScript
- **Database**: SQLite (Development), PostgreSQL (Production - Neon supported)
- **Exports**: openpyxl (Excel), ReportLab (PDF)

## Database Configuration (Neon / PostgreSQL)

To use a PostgreSQL database (like Neon) instead of the default SQLite:

1.  Obtain your PostgreSQL connection string (e.g., from the Neon dashboard). It usually looks like:
    `postgres://user:password@host:port/dbname?sslmode=require`
2.  Set the `DATABASE_URL` environment variable:
    - **Locally**: Create a `.env` file in the root directory and add:
      ```
      DATABASE_URL=your_connection_string_here
      ```
    - **On Vercel**: Go to your project settings -> Environment Variables, and add `DATABASE_URL` with your connection string as the value.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the application:
   ```bash
   python -m app.main
   ```
