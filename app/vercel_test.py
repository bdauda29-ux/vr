from flask import Flask
import os
import sys

app = Flask(__name__)

@app.route("/ping")
def ping():
    results = []
    
    # Test Imports one by one
    try:
        import flask_cors
        results.append("flask_cors: OK")
    except Exception as e:
        results.append(f"flask_cors: FAIL {e}")

    try:
        import sqlalchemy
        results.append("sqlalchemy: OK")
    except Exception as e:
        results.append(f"sqlalchemy: FAIL {e}")

    try:
        import psycopg2
        results.append("psycopg2: OK")
    except Exception as e:
        results.append(f"psycopg2: FAIL {e}")

    try:
        import openpyxl
        results.append("openpyxl: OK")
    except Exception as e:
        results.append(f"openpyxl: FAIL {e}")

    try:
        import reportlab
        results.append("reportlab: OK")
    except Exception as e:
        results.append(f"reportlab: FAIL {e}")
        
    try:
        import passlib
        results.append("passlib: OK")
    except Exception as e:
        results.append(f"passlib: FAIL {e}")

    try:
        import jose
        results.append("jose: OK")
    except Exception as e:
        results.append(f"jose: FAIL {e}")

    return "<br>".join(results)

@app.route("/")
def index():
    return "Index from vercel_test"
