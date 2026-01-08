# Visa/Residency Staff Management System (VSS)

A Flask-based application for managing staff records, leaves, and office assignments within the Visa/Residency Directorate.

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
- **Database**: SQLite
- **Exports**: openpyxl (Excel), ReportLab (PDF)

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the application:
   ```bash
   python -m app.main
   ```
