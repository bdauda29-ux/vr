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

    try:
        # Try importing local modules
        # We need to add the parent directory to sys.path if we are running as a script
        # But Vercel runs as a module usually?
        
        try:
            from . import database
            results.append("local import (from . import database): OK")
        except ImportError:
             import database
             results.append("absolute import (import database): OK")
    except Exception as e:
        results.append(f"local/absolute import of database: FAIL {e}")

    return "<br>".join(results)

@app.route("/")
def index():
    return "Index from vercel_test"
