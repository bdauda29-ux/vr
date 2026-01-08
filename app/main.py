from flask import Flask, request, jsonify, send_from_directory, send_file
import flask
from flask_cors import CORS
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from datetime import date, datetime
try:
    from .database import Base, engine, get_db
    from . import models, schemas, crud, auth, database
    from .seeds import NIGERIA_STATES_LGAS
except ImportError as e:
    # This block catches import errors if database connection fails at module level
    print(f"Import Error: {e}")
    # We still need these to be defined for the app to start, even if they fail later
    Base = None
    engine = None
    get_db = None
    
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
import io
import csv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import tempfile
import os
# from access_parser import AccessParser # Disabled for Vercel compatibility (requires mdb-tools)

app = Flask(__name__, static_folder='static')
app.config["JSON_SORT_KEYS"] = False
CORS(app)

@app.route("/ping")
def ping():
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
    try:
        data = request.get_json(force=True)
        username = data.get("username")
        password = data.get("password")
        
        if not username or not password:
            return jsonify({"detail": "Username and password required"}), 400

        def attempt_login():
            with next(get_db()) as db:
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
    # SKIP DB CHECK ON INDEX to prevent timeouts/crashes on cold start
    # We will let the frontend load, and DB errors will appear when they try to Login.
    return send_from_directory(app.static_folder, "index.html")

@app.route("/debug-db")
def debug_db():
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
    
    return flask.send_file(
        out,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="staff_import_template.xlsx"
    )

@app.post("/import/excel")
def import_excel():
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

with next(get_db()) as db:
    seed_states_lgas(db)
    seed_super_admin(db)

@app.get("/states")
def get_states():
    with next(get_db()) as db:
        items = crud.list_states(db)
        return jsonify([schemas.to_dict_state(s) for s in items])

@app.get("/states/<int:state_id>/lgas")
def get_lgas(state_id: int):
    with next(get_db()) as db:
        items = crud.list_lgas_by_state(db, state_id)
        return jsonify([schemas.to_dict_lga(l) for l in items])

@app.get("/staff")
def list_staff_endpoint():
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
    with next(get_db()) as db:
        obj = crud.get_staff(db, staff_id)
        if not obj:
            return jsonify({"detail": "Not found"}), 404
        return jsonify(schemas.to_dict_staff(obj))

@app.put("/staff/<int:staff_id>")
def update_staff(staff_id: int):
    user = get_current_user()
    if not user:
         return jsonify({"detail": "Not authenticated"}), 401
    
    if user["role"] == "staff":
        if user.get("id") != staff_id:
             return jsonify({"detail": "Permission denied: Can only edit your own record"}), 403
    elif user["role"] not in ["office_admin", "super_admin"]:
         return jsonify({"detail": "Permission denied"}), 403

    data = request.get_json(force=True)
    for k in ("dofa", "dopa", "dopp", "dob", "exit_date"):
        if k in data:
            parsed = parse_date_value(data.get(k))
            if data.get(k) not in (None, "") and parsed is None:
                return jsonify({"detail": f"Invalid date for {k}. Use dd/mm/yyyy"}), 400
            data[k] = parsed
    with next(get_db()) as db:
        obj = crud.get_staff(db, staff_id)
        if not obj:
            return jsonify({"detail": "Not found"}), 404
        obj = crud.update_staff(db, obj, data)
        crud.create_audit_log(db, "UPDATE", f"Staff: {obj.nis_no}", f"Updated fields: {list(data.keys())}")
        return jsonify(schemas.to_dict_staff(obj))

@app.delete("/staff/<int:staff_id>")
def delete_staff(staff_id: int):
    user, err, code = require_role(["super_admin"])
    if err: return err, code

    with next(get_db()) as db:
        obj = crud.get_staff(db, staff_id)
        if not obj:
            return jsonify({"detail": "Not found"}), 404
        nis = obj.nis_no
        crud.delete_staff(db, obj)
        crud.create_audit_log(db, "DELETE", f"Staff: {nis}", "Deleted staff record")
        return "", 204

EXPORT_MAPPING = {
    "nis_no": ("NIS/No", lambda x: x.nis_no),
    "surname": ("Surname", lambda x: x.surname),
    "other_names": ("Other Names", lambda x: x.other_names),
    "rank": ("Rank", lambda x: x.rank),
    "gender": ("Gender", lambda x: x.gender or ""),
    "office": ("Office", lambda x: x.office or ""),
    "state": ("State", lambda x: x.state.name if x.state else ""),
    "lga": ("LGA", lambda x: x.lga.name if x.lga else ""),
    "phone_no": ("Phone", lambda x: x.phone_no or ""),
    "qualification": ("Qualification", lambda x: x.qualification or ""),
    "dob": ("Date of Birth", lambda x: x.dob),
    "dofa": ("DOFA", lambda x: x.dofa),
    "dopa": ("DOPA", lambda x: x.dopa),
    "dopp": ("DOPP", lambda x: x.dopp),
    "exit_date": ("Exit Date", lambda x: x.exit_date),
    "exit_mode": ("Exit Mode", lambda x: x.exit_mode or ""),
    "home_town": ("Home Town", lambda x: x.home_town or ""),
    "next_of_kin": ("Next of Kin", lambda x: x.next_of_kin or ""),
    "nok_phone": ("NOK Phone", lambda x: x.nok_phone or ""),
    "remark": ("Remark", lambda x: x.remark or "")
}

@app.get("/export/excel")
def export_excel():
    q = request.args.get("q")
    state_id = request.args.get("state_id", type=int)
    lga_id = request.args.get("lga_id", type=int)
    rank = request.args.get("rank")
    office = request.args.get("office")
    completeness = request.args.get("completeness")
    columns_str = request.args.get("columns")
    
    with next(get_db()) as db:
        items = crud.list_staff(db, q=q, state_id=state_id, lga_id=lga_id, rank=rank, office=office, completeness=completeness, limit=10000, offset=0)
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Staff List"
        
        # Determine columns
        if columns_str:
            selected_keys = [k for k in columns_str.split(',') if k in EXPORT_MAPPING]
        else:
            selected_keys = ["nis_no", "surname", "other_names", "rank", "gender", "office", "state", "lga", "phone_no", "qualification", "dob", "dofa", "dopa", "dopp", "exit_date", "exit_mode"]
        
        if not selected_keys:
             selected_keys = ["nis_no", "surname", "other_names", "rank"] # Fallback

        headers = [EXPORT_MAPPING[k][0] for k in selected_keys]
        extractors = [EXPORT_MAPPING[k][1] for k in selected_keys]
        
        # Add S/N
        headers.insert(0, "S/N")
        
        row_idx = 1
        num_cols = len(headers)
        
        # 1. Office Name Heading (if filtered)
        if office:
            ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=num_cols)
            cell = ws.cell(row=row_idx, column=1, value=office)
            cell.font = Font(name='Liberation Sans', bold=True, size=14)
            cell.alignment = Alignment(horizontal="center")
            row_idx += 1
            
        # 2. Global Heading
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=num_cols)
        cell = ws.cell(row=row_idx, column=1, value="Visa/Residency Directorate")
        cell.font = Font(name='Liberation Sans', bold=True, size=11)
        cell.alignment = Alignment(horizontal="center")
        row_idx += 1
        
        # Add headers
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=header)
            cell.font = Font(name='Liberation Sans', bold=True)
            cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        row_idx += 1
        
        for idx, item in enumerate(items, 1):
            row_vals = [func(item) for func in extractors]
            row_vals.insert(0, idx) # Insert S/N
            
            fill_color = "FFFFFF" if idx % 2 != 0 else "D9D9D9"
            
            for col_idx, val in enumerate(row_vals, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = Font(name='Liberation Sans')
                cell.fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
                
                # Date Formatting
                if isinstance(val, (date, datetime)):
                    cell.number_format = 'DD/MM/YYYY'
                    cell.alignment = Alignment(horizontal='left')
            row_idx += 1
                    
        # Footer
        ws.oddFooter.left.text = "Generated on &D"
            
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        
        return send_file(
            out,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='staff_list.xlsx'
        )

@app.get("/export/pdf")
def export_pdf():
    q = request.args.get("q")
    state_id = request.args.get("state_id", type=int)
    lga_id = request.args.get("lga_id", type=int)
    rank = request.args.get("rank")
    office = request.args.get("office")
    completeness = request.args.get("completeness")
    columns_str = request.args.get("columns")
    
    with next(get_db()) as db:
        items = crud.list_staff(db, q=q, state_id=state_id, lga_id=lga_id, rank=rank, office=office, completeness=completeness, limit=10000, offset=0)
        
        def add_footer(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 9)
            date_str = datetime.now().strftime("%d/%m/%Y")
            canvas.drawString(inch, 0.5 * inch, f"Generated on {date_str}")
            canvas.restoreState()
            
        out = io.BytesIO()
        doc = SimpleDocTemplate(out, pagesize=landscape(letter))
        elements = []
        
        styles = getSampleStyleSheet()
        
        # Custom Styles
        title_style = styles['Title']
        title_style.fontName = 'Helvetica-Bold'
        title_style.fontSize = 14
        
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=11,
            alignment=1, # Center
            spaceAfter=12
        )
        
        # 1. Office Heading
        if office:
            p_office = Paragraph(office, title_style)
            elements.append(p_office)
            
        # 2. Global Heading
        p_global = Paragraph("Visa/Residency Directorate", subtitle_style)
        elements.append(p_global)
        
        elements.append(Spacer(1, 12))
        
        # Determine columns
        if columns_str:
            selected_keys = [k for k in columns_str.split(',') if k in EXPORT_MAPPING]
        else:
             # Default for PDF (fewer columns to fit)
            selected_keys = ["nis_no", "surname", "other_names", "rank", "dopa", "gender", "office", "state", "phone_no"]
            
        if not selected_keys:
             selected_keys = ["nis_no", "surname", "other_names", "rank"]

        headers = [EXPORT_MAPPING[k][0] for k in selected_keys]
        extractors = [EXPORT_MAPPING[k][1] for k in selected_keys]
        
        # Add S/N
        headers.insert(0, "S/N")
        
        data = [headers]
        
        for idx, item in enumerate(items, 1):
            row = []
            for func in extractors:
                val = func(item)
                if isinstance(val, (date, datetime)):
                    val = val.strftime('%d/%m/%Y')
                elif val is None:
                    val = ""
                row.append(val)
            row.insert(0, idx) # Insert S/N
            data.append(row)
            
        table = Table(data)
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'), # Header Center
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8), # Smaller font for headers
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black), # Thinner grid lines
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7), # Smaller font for data
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#D9D9D9')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        elements.append(table)
        doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)
        out.seek(0)
        
        return send_file(
            out,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='staff_list.pdf'
        )


@app.get("/dashboard/stats")
def get_dashboard_stats():
    user = get_current_user()
    if not user:
        return jsonify({"detail": "Not authenticated"}), 401
    
    with next(get_db()) as db:
        stats = crud.get_dashboard_stats(db)
        return jsonify(stats)

@app.get("/offices")
def list_offices_endpoint():
    # Sync offices if empty (Lazy sync)
    with next(get_db()) as db:
        offices = crud.list_offices_model(db)
        if not offices:
            # Populate from staff
            names = crud.list_offices(db)
            for n in names:
                if n:
                    crud.create_office(db, n)
            offices = crud.list_offices_model(db)
        return jsonify([schemas.to_dict_office(o) for o in offices])

@app.post("/offices")
def create_office_endpoint():
    user, err, code = require_role(["super_admin", "office_admin", "admin"]) # Allow admin to add offices?
    if err: return err, code
    
    data = request.get_json()
    name = data.get("name")
    if not name:
        return jsonify({"detail": "Name required"}), 400
        
    with next(get_db()) as db:
        try:
            office = crud.create_office(db, name)
            return jsonify(schemas.to_dict_office(office))
        except Exception as e:
            return jsonify({"detail": str(e)}), 400

@app.put("/offices/<int:office_id>")
def update_office_endpoint(office_id):
    user, err, code = require_role(["super_admin", "office_admin", "admin"])
    if err: return err, code
    
    data = request.get_json()
    name = data.get("name")
    if not name:
        return jsonify({"detail": "Name required"}), 400
        
    with next(get_db()) as db:
        office = crud.update_office(db, office_id, name)
        if not office:
            return jsonify({"detail": "Office not found"}), 404
        return jsonify(schemas.to_dict_office(office))

@app.delete("/offices/<int:office_id>")
def delete_office_endpoint(office_id):
    user, err, code = require_role(["super_admin", "office_admin", "admin"])
    if err: return err, code
    
    with next(get_db()) as db:
        success = crud.delete_office(db, office_id)
        if not success:
            return jsonify({"detail": "Office not found"}), 404
        return jsonify({"detail": "Deleted"})

@app.get("/audit-logs")
def list_audit_logs():
    user, err, code = require_role(["super_admin"])
    if err: return err, code

    limit = request.args.get("limit", default=100, type=int)
    offset = request.args.get("offset", default=0, type=int)
    with next(get_db()) as db:
        items = crud.list_audit_logs(db, limit=limit, offset=offset)
        return jsonify([schemas.to_dict_audit_log(x) for x in items])

@app.put("/staff/<int:staff_id>/role")
def update_staff_role(staff_id: int):
    # Verify Super Admin
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({"detail": "Not authenticated"}), 401
    
    token = auth_header.split(" ")[1]
    payload = auth.decode_access_token(token)
    if not payload or payload.get("role") != "super_admin":
        return jsonify({"detail": "Permission denied"}), 403
    
    data = request.get_json()
    new_role = data.get("role")
    if new_role not in ["staff", "office_admin", "super_admin"]:
        return jsonify({"detail": "Invalid role"}), 400
        
    with next(get_db()) as db:
        staff = crud.get_staff(db, staff_id)
        if not staff:
            return jsonify({"detail": "Staff not found"}), 404
            
        staff.role = new_role
        db.commit()
        return jsonify({"message": f"Role updated to {new_role}"})

@app.post("/leaves")
def create_leave_request():
    user = get_current_user()
    if not user:
        return jsonify({"detail": "Not authenticated"}), 401
    
    data = request.get_json()
    
    with next(get_db()) as db:
        staff_id = None
        if user["role"] == "staff":
            staff_id = user["id"]
        elif user["role"] in ["admin", "super_admin", "office_admin"]:
            staff_id = data.get("staff_id")
            if not staff_id:
                return jsonify({"detail": "Staff ID required for admin creation"}), 400
        else:
            return jsonify({"detail": "Permission denied"}), 403

        if not staff_id:
             return jsonify({"detail": "Could not determine Staff ID"}), 400

        leave_data = {
            "staff_id": staff_id,
            "start_date": parse_date_value(data.get("start_date")),
            "end_date": parse_date_value(data.get("end_date")),
            "leave_type": data.get("leave_type"),
            "reason": data.get("reason"),
            "status": "Pending"
        }
        
        if not leave_data["start_date"] or not leave_data["end_date"] or not leave_data["leave_type"]:
             return jsonify({"detail": "Missing required fields"}), 400
             
        leave = crud.create_leave(db, leave_data)
        
        # Audit Log
        actor = user.get("sub", "Unknown")
        crud.create_audit_log(db, "CREATE_LEAVE", f"Leave request for Staff ID {staff_id}", f"Type: {leave_data['leave_type']}")
        
        return jsonify(schemas.to_dict_leave(leave))

@app.get("/leaves")
def list_leaves_endpoint():
    user = get_current_user()
    if not user:
        return jsonify({"detail": "Not authenticated"}), 401
    
    with next(get_db()) as db:
        if user["role"] == "staff":
            leaves = crud.list_leaves(db, staff_id=user["id"])
        else:
            # Admin sees all, or filtered
            staff_id = request.args.get("staff_id")
            status = request.args.get("status")
            leaves = crud.list_leaves(db, staff_id=staff_id, status=status)
            
        return jsonify([schemas.to_dict_leave(l) for l in leaves])

@app.put("/leaves/<int:leave_id>")
def update_leave_status_endpoint(leave_id):
    user, err, code = require_role(["super_admin", "office_admin"])
    if err: return err, code
        
    data = request.get_json()
    status = data.get("status")
    
    if status not in ["Approved", "Rejected", "Pending"]:
        return jsonify({"detail": "Invalid status"}), 400
        
    with next(get_db()) as db:
        leave = crud.update_leave_status(db, leave_id, status)
        if not leave:
            return jsonify({"detail": "Leave not found"}), 404
            
        # Audit Log
        actor = user.get("sub", "Unknown")
        crud.create_audit_log(db, "UPDATE_LEAVE", f"Leave ID {leave_id} status to {status}", f"By {actor}")
        
        return jsonify(schemas.to_dict_leave(leave))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
