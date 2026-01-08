import sys
import os
import traceback
from flask import Flask, request, jsonify, send_from_directory, send_file

# 1. Initialize Flask App IMMEDIATELY
# This ensures 'app' exists even if other imports fail
app = Flask(__name__, static_folder='static')
app.config["JSON_SORT_KEYS"] = False

# 2. Define Global Error State
STARTUP_ERROR = None
cors_enabled = False

# 3. Safe Imports
# We import everything else inside a try/except block
try:
    # Flask CORS
    try:
        from flask_cors import CORS
        CORS(app)
        cors_enabled = True
    except ImportError:
        print("WARNING: flask_cors not found. CORS disabled.")
    except Exception as e:
        print(f"WARNING: CORS init failed: {e}")

    # Standard Libs
    from datetime import date, datetime
    import io
    import csv
    import tempfile
    
    # Third Party
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    
    # SQLAlchemy
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import OperationalError

    # Local Imports
    # NOTE: We use relative imports assuming Vercel runs this as a module
    from .database import Base, engine, get_db
    from . import models, schemas, crud, auth, database
    from .seeds import NIGERIA_STATES_LGAS

except Exception as e:
    # Catch ALL errors during import/init
    STARTUP_ERROR = f"Startup Error: {str(e)}\n{traceback.format_exc()}"
    print(STARTUP_ERROR) # Print to Vercel logs
    
    # Define dummy objects to prevent NameErrors below
    Base = None
    engine = None
    get_db = lambda: (yield None)
    models = None
    schemas = None
    crud = None
    auth = None
    database = None
    NIGERIA_STATES_LGAS = {}
    
    # Dummy classes for types
    class Font: pass
    class Alignment: pass
    class PatternFill: pass

@app.route("/ping")
def ping():
    if STARTUP_ERROR:
        return jsonify({"status": "error", "message": STARTUP_ERROR}), 500
    return "pong"

# --- AUTH ---
@app.route("/login.html")
def login_page():
    return send_from_directory(app.static_folder, "login.html")

@app.route("/success.html")
def success_page():
    return send_from_directory(app.static_folder, "success.html")

@app.post("/login")
def login():
    if STARTUP_ERROR: return jsonify({"detail": STARTUP_ERROR}), 500
    try:
        data = request.get_json(force=True)
        username = data.get("username")
        password = data.get("password")
        
        if not username or not password:
            return jsonify({"detail": "Username and password required"}), 400

        def attempt_login():
            with next(get_db()) as db:
                if not db: raise Exception("Database connection failed")
                # 1. Check if Admin/Super Admin
                user = db.query(models.User).filter(models.User.username == username).first()
                if user:
                    if auth.verify_password(password, user.password_hash):
                        token = auth.create_access_token(data={"sub": user.username, "role": user.role, "id": user.id})
                        return jsonify({"access_token": token, "token_type": "bearer", "role": user.role, "username": user.username})
                
                # 2. Check if Staff (NIS is username and password)
                staff = crud.get_staff_by_nis(db, username)
                if staff:
                    if password == staff.nis_no: # Staff Password IS their NIS
                        token = auth.create_access_token(data={"sub": staff.nis_no, "role": staff.role, "id": staff.id})
                        return jsonify({"access_token": token, "token_type": "bearer", "role": staff.role, "username": staff.nis_no})
                
                return jsonify({"detail": "Invalid credentials"}), 401

        try:
            return attempt_login()
        except Exception as e:
            # Check for missing tables (SQLite or Postgres)
            msg = str(e).lower()
            if "no such table" in msg or ("relation" in msg and "does not exist" in msg):
                print("Tables missing, attempting creation...")
                if engine:
                    Base.metadata.create_all(bind=engine)
                    # Seed default admin
                    with next(get_db()) as temp_db:
                         from .seeds import seed_default_admin
                         seed_default_admin(temp_db)
                    # Retry login
                    return attempt_login()
            raise e

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Log critical info for debugging Vercel issues
        print(f"LOGIN CRASH: {e}") 
        return jsonify({
            "detail": "Login failed due to server error",
            "error": str(e)
        }), 500

@app.get("/me")
def get_current_user_info():
    if STARTUP_ERROR: return jsonify({"detail": STARTUP_ERROR}), 500
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"detail": "Not authenticated"}), 401
    
    token = auth_header.split(" ")[1]
    payload = auth.decode_access_token(token)
    if not payload:
        return jsonify({"detail": "Invalid token"}), 401
    
    return jsonify(payload)

# --- END AUTH ---

def parse_date_value(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        try:
            return date.fromisoformat(s.split("T", 1)[0])
        except ValueError:
            return None
    return None

# --- AUTH HELPERS ---
def get_current_user():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(" ")[1]
    return auth.decode_access_token(token)

def require_role(allowed_roles):
    user = get_current_user()
    if not user:
        return None, jsonify({"detail": "Not authenticated"}), 401
    if user["role"] not in allowed_roles:
        return None, jsonify({"detail": "Permission denied"}), 403
    return user, None, None

# --- END AUTH HELPERS ---

@app.route("/")
def index():
    if STARTUP_ERROR:
        return f"<h1>System Error</h1><pre>{STARTUP_ERROR}</pre>"
    # SKIP DB CHECK ON INDEX to prevent timeouts/crashes on cold start
    # We will let the frontend load, and DB errors will appear when they try to Login.
    return send_from_directory(app.static_folder, "index.html")

@app.route("/debug-db")
def debug_db():
    if STARTUP_ERROR: return jsonify({"status": "error", "message": STARTUP_ERROR}), 500
    if not engine:
        return jsonify({"status": "error", "detail": "Database engine not initialized. Check logs."}), 500
        
    try:
        # Check if table exists
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # Try a simple query
        try:
            with next(get_db()) as db:
                version = db.execute(text("SELECT version()")).scalar()
                
                # Attempt to init tables if missing
                if "users" not in tables:
                    Base.metadata.create_all(bind=engine)
                    from .seeds import seed_default_admin
                    seed_default_admin(db)
                    tables = inspector.get_table_names()
        except Exception as query_err:
             return jsonify({
                "status": "error",
                "detail": "Connection successful but query failed",
                "error": str(query_err)
            }), 500

        return jsonify({
            "status": "ok",
            "db_version": version,
            "tables": tables,
            "message": "Connected successfully"
        })
    except Exception as e:
        import traceback
        return jsonify({
            "status": "error",
            "detail": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.get("/download/template")
def download_template():
    if STARTUP_ERROR: return jsonify({"detail": STARTUP_ERROR}), 500
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Staff Import Template"
    
    # Headers
    headers = [
        "NIS/No", "Surname", "Other Names", "Rank", "Gender", 
        "State of Origin", "LGA", "Office", "Phone No", 
        "Qualification", "Home Town", "Next of Kin", "NOK Phone", 
        "Remark", "DOFA", "DOPA", "DOPP", "DOB"
    ]
    ws.append(headers)
    
    # Sample Row (Optional)
    ws.append([
        "12345", "Doe", "John", "ASI 1", "Male", 
        "Lagos", "Ikeja", "Visa Counter", "08012345678", 
        "B.Sc", "Ikeja", "Jane Doe", "08098765432", 
        "Sample entry", "01/01/2010", "01/01/2015", "01/01/2020", "15/05/1985"
    ])
    
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    
    return send_file(
        out,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="staff_import_template.xlsx"
    )

@app.post("/import/excel")
def import_excel():
    if STARTUP_ERROR: return jsonify({"detail": STARTUP_ERROR}), 500
    user, err, code = require_role(["office_admin", "super_admin"])
    if err: return err, code

    if 'file' not in request.files:
        return jsonify({"detail": "No file uploaded"}), 400
    file = request.files['file']
    filename = file.filename.lower()
    
    if not filename.endswith(('.xlsx', '.xls')):
        return jsonify({"detail": "Invalid file type. Please upload Excel (.xlsx, .xls) file."}), 400
    
    # Save to /tmp for Vercel compatibility
    tmp_dir = tempfile.gettempdir()
    tmp_path = os.path.join(tmp_dir, filename)
    file.save(tmp_path)

    try:
        data_rows = [] # List of dicts {col_name: value}
        wb = None
        
        if filename.endswith(('.xlsx', '.xls')):
            wb = openpyxl.load_workbook(tmp_path)
            ws = wb.active
            headers = [cell.value for cell in ws[1]]
            col_map = {h: i for i, h in enumerate(headers) if h}
            
            for row in ws.iter_rows(min_row=2, values_only=True):
                # Convert row tuple to dict
                row_dict = {}
                for h, i in col_map.items():
                    row_dict[h] = row[i]
                data_rows.append(row_dict)
                            
        # Common processing
        success_count = 0
        errors = []
        required_cols = {"NIS/No", "Surname", "Other Names", "Rank", "Gender"}
        
        # Normalize column names in data_rows to match required_cols
        # Access might have "NIS_No" instead of "NIS/No" etc.
        # We need a robust getter.

        with next(get_db()) as db_session:
             # Cache states/LGAs
            states_cache = {s.name.lower(): s.id for s in db_session.query(models.State).all()}
            
            for row_idx, row_dict in enumerate(data_rows, start=1):
                try:
                    # Helper to get value with fuzzy key matching
                    def get_val(target_key):
                        # 1. Exact match
                        if target_key in row_dict:
                            return row_dict[target_key]
                        # 2. Case insensitive
                        for k, v in row_dict.items():
                            if k.lower() == target_key.lower():
                                return v
                        # 3. Special handling for NIS/No
                        if target_key == "NIS/No":
                            for k in row_dict.keys():
                                if k.lower().replace("_", "").replace("/", "") == "nisno" or k.lower() == "nis":
                                    return row_dict[k]
                        return None
                        
                    def get_text_val(key):
                        val = get_val(key)
                        if val is None: return None
                        s = str(val).strip()
                        return s if s else None

                    nis = get_text_val("NIS/No")
                    if not nis: continue
                    
                    data = {
                        "nis_no": nis,
                        "surname": get_text_val("Surname"),
                        "other_names": get_text_val("Other Names"),
                        "rank": get_text_val("Rank"),
                        "gender": get_text_val("Gender"),
                        "office": get_text_val("Office"),
                        "phone_no": get_text_val("Phone No") or get_text_val("Phone"),
                        "qualification": get_text_val("Qualification"),
                        "home_town": get_text_val("Home Town"),
                        "next_of_kin": get_text_val("Next of Kin"),
                        "nok_phone": get_text_val("NOK Phone"),
                        "remark": get_text_val("Remark"),
                        "dofa": parse_date_value(get_val("DOFA")),
                        "dopa": parse_date_value(get_val("DOPA")),
                        "dopp": parse_date_value(get_val("DOPP")),
                        "dob": parse_date_value(get_val("DOB")),
                    }
                    
                    # Validate required
                    if not data["surname"] or not data["rank"]:
                        raise ValueError("Missing Surname or Rank")
                    if not data["gender"]:
                        raise ValueError("Missing Gender")
                        
                    # Handle State/LGA
                    s_name = get_text_val("State of Origin") or get_text_val("State")
                    if s_name and s_name.lower() in states_cache:
                        data["state_id"] = states_cache[s_name.lower()]
                        l_name = get_text_val("LGA")
                        if l_name:
                            lga_obj = db_session.query(models.LGA).filter(
                                models.LGA.state_id == data["state_id"],
                                models.LGA.name == l_name
                            ).first()
                            if not lga_obj:
                                lga_obj = models.LGA(name=l_name, state_id=data["state_id"])
                                db_session.add(lga_obj)
                                db_session.flush()
                            data["lga_id"] = lga_obj.id

                    crud.create_staff(db_session, data)
                    success_count += 1
                except Exception as e:
                    db_session.rollback()
                    errors.append(f"Row {row_idx}: {str(e)}")
            
            if success_count > 0:
                crud.create_audit_log(db_session, "IMPORT", filename, f"Imported {success_count} records")

            db_session.commit()
            
        return jsonify({
            "message": f"Imported {success_count} records",
            "errors": errors[:10]
        })

    except Exception as e:
        return jsonify({"detail": f"Failed to process file: {str(e)}"}), 500
    finally:
        if 'wb' in locals() and wb:
            wb.close()
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception as e:
                print(f"Warning: Could not remove temp file {tmp_path}: {e}")

# Init DB on startup if possible
if engine:
    try:
        Base.metadata.create_all(bind=engine)
        
        def seed_states_lgas(db: Session):
            # 1. Ensure all states exist
            existing_states = {s.name: s for s in db.query(models.State).all()}
            
            for state_name in NIGERIA_STATES_LGAS:
                if state_name not in existing_states:
                    s = models.State(name=state_name)
                    db.add(s)
                    # Add to local dict for next step, though ID won't be available until flush
                    existing_states[state_name] = s
            
            db.flush() # Flush to get IDs for new states
            
            # Refresh existing_states map to ensure we have IDs
            existing_states = {s.name: s for s in db.query(models.State).all()}
            
            # 2. Ensure all LGAs exist
            # Fetch all existing LGAs to avoid duplicates
            existing_lgas = set()
            for l in db.query(models.LGA).all():
                existing_lgas.add((l.state_id, l.name))
                
            for state_name, lgas in NIGERIA_STATES_LGAS.items():
                if state_name in existing_states:
                    st = existing_states[state_name]
                    for lga_name in lgas:
                        if (st.id, lga_name) not in existing_lgas:
                            db.add(models.LGA(name=lga_name, state_id=st.id))
                            existing_lgas.add((st.id, lga_name)) # Update local set
                            
            db.commit()

        def seed_super_admin(db: Session):
            admin = db.query(models.User).filter(models.User.username == "admin").first()
            if not admin:
                # Default password: admin
                pwd_hash = auth.get_password_hash("admin")
                admin = models.User(username="admin", password_hash=pwd_hash, role="super_admin")
                db.add(admin)
                db.commit()

        # We can't use next(get_db()) here easily because of context manager
        # Just use SessionLocal direct
        from .database import SessionLocal
        db = SessionLocal()
        try:
            seed_states_lgas(db)
            seed_super_admin(db)
        finally:
            db.close()
            
    except Exception as e:
        print(f"DB Init Warning: {e}")
        # We don't crash here, just log

@app.get("/states")
def get_states():
    if STARTUP_ERROR: return jsonify({"detail": STARTUP_ERROR}), 500
    with next(get_db()) as db:
        items = crud.list_states(db)
        return jsonify([schemas.to_dict_state(s) for s in items])

@app.get("/states/<int:state_id>/lgas")
def get_lgas(state_id: int):
    if STARTUP_ERROR: return jsonify({"detail": STARTUP_ERROR}), 500
    with next(get_db()) as db:
        items = crud.list_lgas_by_state(db, state_id)
        return jsonify([schemas.to_dict_lga(l) for l in items])

@app.get("/staff")
def list_staff_endpoint():
    if STARTUP_ERROR: return jsonify({"detail": STARTUP_ERROR}), 500
    user = get_current_user()
    if not user:
        return jsonify({"detail": "Not authenticated"}), 401
    
    q = request.args.get("q")
    state_id = request.args.get("state_id", type=int)
    lga_id = request.args.get("lga_id", type=int)
    rank = request.args.get("rank")
    office = request.args.get("office")
    completeness = request.args.get("completeness")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    
    with next(get_db()) as db:
        # Role Restriction
        if user["role"] == "office_admin":
            # Fetch user's office
            staff_user = crud.get_staff(db, user["id"])
            if not staff_user or not staff_user.office:
                return jsonify([]), 200 # No office assigned, see nothing?
            # Enforce office filter
            office = staff_user.office
            
        items = crud.list_staff(
            db, q=q, state_id=state_id, lga_id=lga_id, 
            rank=rank, office=office, completeness=completeness,
            limit=limit, offset=offset
        )
        return jsonify([schemas.to_dict_staff(item) for item in items])

@app.post("/staff")
def create_staff():
    if STARTUP_ERROR: return jsonify({"detail": STARTUP_ERROR}), 500
    user, error_response, code = require_role(["office_admin", "super_admin"])
    if error_response:
        return error_response, code

    data = request.get_json(force=True)
    required = ["nis_no","surname","other_names","rank"]
    for k in required:
        if k not in data or not str(data[k]).strip():
            return jsonify({"detail": f"{k} is required"}), 400
    for k in ("dofa", "dopa", "dopp", "dob", "exit_date"):
        if k in data:
            parsed = parse_date_value(data.get(k))
            if data.get(k) not in (None, "") and parsed is None:
                return jsonify({"detail": f"Invalid date for {k}. Use dd/mm/yyyy"}), 400
            data[k] = parsed
            
    # Ensure gender is at least empty string if not provided (to satisfy potential DB NOT NULL if migration didn't happen)
    if "gender" not in data or data["gender"] is None:
        data["gender"] = ""
        
    with next(get_db()) as db:
        try:
            obj = crud.create_staff(db, data)
            crud.create_audit_log(db, "CREATE", f"Staff: {obj.nis_no}", "Created new staff")
            return jsonify(schemas.to_dict_staff(obj)), 201
        except ValueError as e:
            return jsonify({"detail": str(e)}), 400

@app.get("/staff/<int:staff_id>")
def get_staff(staff_id: int):
    if STARTUP_ERROR: return jsonify({"detail": STARTUP_ERROR}), 500
    with next(get_db()) as db:
        obj = crud.get_staff(db, staff_id)
        if not obj:
            return jsonify({"detail": "Not found"}), 404
        return jsonify(schemas.to_dict_staff(obj))

@app.put("/staff/<int:staff_id>")
def update_staff(staff_id: int):
    if STARTUP_ERROR: return jsonify({"detail": STARTUP_ERROR}), 500
    user = get_current_user()
    if not user:
        return jsonify({"detail": "Not authenticated"}), 401
        
    data = request.get_json(force=True)
    for k in ("dofa", "dopa", "dopp", "dob", "exit_date"):
        if k in data:
             data[k] = parse_date_value(data.get(k))
             
    with next(get_db()) as db:
        # Check permissions
        existing = crud.get_staff(db, staff_id)
        if not existing:
             return jsonify({"detail": "Not found"}), 404
             
        if user["role"] == "office_admin":
             # Can only edit own office
             staff_user = crud.get_staff(db, user["id"])
             if not staff_user or staff_user.office != existing.office:
                 return jsonify({"detail": "Permission denied"}), 403
        
        try:
            obj = crud.update_staff(db, staff_id, data)
            if obj:
                crud.create_audit_log(db, "UPDATE", f"Staff: {obj.nis_no}", "Updated staff details")
                return jsonify(schemas.to_dict_staff(obj))
            return jsonify({"detail": "Not found"}), 404
        except ValueError as e:
            return jsonify({"detail": str(e)}), 400

@app.delete("/staff/<int:staff_id>")
def delete_staff(staff_id: int):
    if STARTUP_ERROR: return jsonify({"detail": STARTUP_ERROR}), 500
    user, err, code = require_role(["super_admin"])
    if err: return err, code
    
    with next(get_db()) as db:
        if crud.delete_staff(db, staff_id):
            crud.create_audit_log(db, "DELETE", f"Staff ID: {staff_id}", "Deleted staff record")
            return jsonify({"detail": "Deleted"})
        return jsonify({"detail": "Not found"}), 404

@app.get("/export/excel")
def export_excel():
    if STARTUP_ERROR: return jsonify({"detail": STARTUP_ERROR}), 500
    user = get_current_user()
    if not user: return jsonify({"detail": "Not authenticated"}), 401
    
    with next(get_db()) as db:
        staff_list = crud.list_staff(db, limit=10000)
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Staff List"
        
        # Style: Liberation Sans
        font_style = Font(name='Liberation Sans', size=10)
        header_font = Font(name='Liberation Sans', size=12, bold=True)
        
        # Headers
        headers = ["NIS/No", "Surname", "Other Names", "Rank", "Gender", "Office", "State", "LGA", "Phone"]
        ws.append(headers)
        
        for cell in ws[1]:
            cell.font = header_font
            
        # Data
        for idx, staff in enumerate(staff_list, start=2):
            row = [
                staff.nis_no, staff.surname, staff.other_names, staff.rank, staff.gender,
                staff.office, 
                staff.state.name if staff.state else "",
                staff.lga.name if staff.lga else "",
                staff.phone_no
            ]
            ws.append(row)
            
            # Zebra Striping
            if idx % 2 == 0:
                fill = PatternFill(start_color="F0F0F0", end_color="F0F0F0", fill_type="solid")
                for cell in ws[idx]:
                    cell.fill = fill
            
            # Apply Font
            for cell in ws[idx]:
                cell.font = font_style

        # Footer Date
        ws.append([])
        footer_cell = ws.cell(row=ws.max_row + 1, column=1, value=f"Generated on {datetime.now().strftime('%d/%m/%Y')}")
        footer_cell.font = Font(name='Liberation Sans', size=8, italic=True)
        
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        
        return send_file(
            out,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"staff_export_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
