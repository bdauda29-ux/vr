from typing import Optional, List, Union, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, case, func, distinct, text
from datetime import date, datetime
import bcrypt
from . import models

# Rank order mapping (Highest to Lowest)
RANK_ORDER = [
    "CGI", "DCG", "ACG", "CIS", "DCI", "ACI", "CSI", "SI", "DSI",
    "ASI 1", "ASI 2", "II", "AII", "IA 1", "IA 2", "IA 3"
]

def list_states(db: Session) -> List[models.State]:
    return list(db.scalars(select(models.State).order_by(models.State.name)))

def list_lgas_by_state(db: Session, state_id: int) -> List[models.LGA]:
    return list(db.scalars(select(models.LGA).where(models.LGA.state_id == state_id).order_by(models.LGA.name)))

def get_staff(db: Session, staff_id: int) -> Optional[models.Staff]:
    return db.get(models.Staff, staff_id)

def get_staff_by_nis(db: Session, nis_no: str) -> Optional[models.Staff]:
    return db.scalar(select(models.Staff).where(models.Staff.nis_no == nis_no))

def list_staff(
    db: Session,
    q: Optional[str] = None,
    state_id: Optional[Union[int, List[int]]] = None,
    lga_id: Optional[Union[int, List[int]]] = None,
    rank: Optional[Union[str, List[str]]] = None,
    office: Optional[Union[str, List[str]]] = None,
    completeness: Optional[str] = None,
    status: Optional[str] = "active",
    dopp_order: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    exit_from=None,
    exit_to=None,
    dopa_from=None,
    dopa_to=None,
    formation_id: Optional[Union[int, List[int]]] = None,
    include_count: bool = False,
    gender: Optional[Union[str, List[str]]] = None,
    retirement_year: Optional[int] = None
) -> Union[List[models.Staff], Tuple[List[models.Staff], int]]:
    # Build Rank Sorting Logic
    # We want to sort by Rank (Custom Order), then DOPA (Date of Present Appointment), then NIS No
    
    # Create a CASE statement for rank ordering
    # Assign index 0 to highest rank, 1 to next, etc.
    # If rank is not in list, put it at the end (e.g. 999)
    whens = {name: i for i, name in enumerate(RANK_ORDER)}
    rank_sort = case(
        whens, 
        value=models.Staff.rank, 
        else_=999
    )
    
    stmt = select(models.Staff)
    
    if status == "active":
        stmt = stmt.where(models.Staff.exit_date.is_(None))
    elif status == "exited":
        stmt = stmt.where(models.Staff.exit_date.is_not(None))
        if exit_from is not None:
            stmt = stmt.where(models.Staff.exit_date >= exit_from)
        if exit_to is not None:
            stmt = stmt.where(models.Staff.exit_date <= exit_to)

    if dopa_from is not None:
        stmt = stmt.where(models.Staff.dopa >= dopa_from)
    if dopa_to is not None:
        stmt = stmt.where(models.Staff.dopa <= dopa_to)

    if state_id is not None:
        if isinstance(state_id, list):
            stmt = stmt.where(models.Staff.state_id.in_(state_id))
        else:
            stmt = stmt.where(models.Staff.state_id == state_id)

    if lga_id is not None:
        if isinstance(lga_id, list):
            stmt = stmt.where(models.Staff.lga_id.in_(lga_id))
        else:
            stmt = stmt.where(models.Staff.lga_id == lga_id)

    if gender:
        if isinstance(gender, list):
            stmt = stmt.where(models.Staff.gender.in_(gender))
        else:
            stmt = stmt.where(models.Staff.gender == gender)
    if rank:
        if isinstance(rank, list):
             stmt = stmt.where(models.Staff.rank.in_(rank))
        else:
             stmt = stmt.where(models.Staff.rank == rank)
    if office:
        if isinstance(office, list):
             stmt = stmt.where(models.Staff.office.in_(office))
        else:
             stmt = stmt.where(models.Staff.office == office)
             
    if formation_id is not None:
        if isinstance(formation_id, list):
            stmt = stmt.where(models.Staff.formation_id.in_(formation_id))
        else:
            stmt = stmt.where(models.Staff.formation_id == formation_id)
    
    if retirement_year:
        # PostgreSQL syntax
        if db.bind.dialect.name == 'postgresql':
            ret_date_expr = func.least(
                models.Staff.dob + text("INTERVAL '60 years'"),
                models.Staff.dofa + text("INTERVAL '35 years'")
            )
            stmt = stmt.where(func.extract('year', ret_date_expr) == retirement_year)
        else:
            # SQLite fallback
            ret_date_expr = func.min(
                func.date(models.Staff.dob, '+60 years'),
                func.date(models.Staff.dofa, '+35 years')
            )
            stmt = stmt.where(func.strftime('%Y', ret_date_expr) == str(retirement_year))

    if completeness == "completed":
        # Criteria: Must have all critical fields filled
        stmt = stmt.where(
            models.Staff.surname.is_not(None), models.Staff.surname != "",
            models.Staff.other_names.is_not(None), models.Staff.other_names != "",
            models.Staff.rank.is_not(None), models.Staff.rank != "",
            models.Staff.gender.is_not(None), models.Staff.gender != "",
            models.Staff.dob.is_not(None),
            models.Staff.phone_no.is_not(None), models.Staff.phone_no != "",
            models.Staff.state_id.is_not(None),
            models.Staff.lga_id.is_not(None),
            models.Staff.office.is_not(None), models.Staff.office != "",
            models.Staff.dofa.is_not(None),
            models.Staff.dopa.is_not(None),
            models.Staff.dopp.is_not(None)
        )
    elif completeness == "incomplete":
        # Criteria: Missing ANY of the critical fields
        stmt = stmt.where(
            or_(
                models.Staff.surname.is_(None), models.Staff.surname == "",
                models.Staff.other_names.is_(None), models.Staff.other_names == "",
                models.Staff.rank.is_(None), models.Staff.rank == "",
                models.Staff.gender.is_(None), models.Staff.gender == "",
                models.Staff.dob.is_(None),
                models.Staff.phone_no.is_(None), models.Staff.phone_no == "",
                models.Staff.state_id.is_(None),
                models.Staff.lga_id.is_(None),
                models.Staff.office.is_(None), models.Staff.office == "",
                models.Staff.dofa.is_(None),
                models.Staff.dopa.is_(None),
                models.Staff.dopp.is_(None)
            )
        )

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                models.Staff.surname.ilike(like),
                models.Staff.other_names.ilike(like),
                models.Staff.nis_no.ilike(like),
                models.Staff.phone_no.ilike(like),
                models.Staff.office.ilike(like),
            )
        )

    total_count = 0
    if include_count:
        # Clone query for count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = db.scalar(count_stmt) or 0

    # Apply sorting
    if status == "exited" and dopp_order in ("asc", "desc"):
        stmt = stmt.order_by(
            models.Staff.exit_date.asc() if dopp_order == "asc" else models.Staff.exit_date.desc(),
            models.Staff.nis_no
        )
    elif dopp_order in ("asc", "desc"):
        stmt = stmt.order_by(
            models.Staff.dopp.asc() if dopp_order == "asc" else models.Staff.dopp.desc(),
            models.Staff.nis_no
        )
    elif dopp_order in ("retirement_asc", "retirement_desc"):
        # Check dialect
        dialect = db.bind.dialect.name
        
        if dialect == "postgresql":
            # Postgres specific: Use INTERVAL and LEAST
            # Cast literal to Date for coalesce compatibility
            high_date = func.cast('9999-12-31', models.Date)
            
            dob_plus_60 = models.Staff.dob + text("INTERVAL '60 years'")
            dofa_plus_35 = models.Staff.dofa + text("INTERVAL '35 years'")
            
            ret_date = func.least(
                func.coalesce(dob_plus_60, high_date),
                func.coalesce(dofa_plus_35, high_date)
            )
             # CGI Exempt (infinite retirement)
            sort_expr = case(
                (models.Staff.rank == 'CGI', high_date),
                else_=ret_date
            )
        else:
            # SQLite fallback (existing logic)
            # Calculate retirement date: MIN(DOB+60, DOFA+35)
            # Handle missing dates by defaulting to high date (9999-12-31) so they don't block MIN
            ret_date = func.min(
                func.coalesce(func.date(models.Staff.dob, '+60 years'), '9999-12-31'),
                func.coalesce(func.date(models.Staff.dofa, '+35 years'), '9999-12-31')
            )
            # CGI Exempt (infinite retirement)
            sort_expr = case(
                (models.Staff.rank == 'CGI', '9999-12-31'),
                else_=ret_date
            )
            
        stmt = stmt.order_by(
            sort_expr.asc() if dopp_order == "retirement_asc" else sort_expr.desc(),
            models.Staff.nis_no
        )
    else:
        stmt = stmt.order_by(
            rank_sort, 
            models.Staff.dopa.asc(),
            models.Staff.nis_no
        )
    
    stmt = stmt.offset(offset).limit(limit)
    
    items = list(db.scalars(stmt))
    
    if include_count:
        return items, total_count
    return items

def create_staff(db: Session, data: dict) -> models.Staff:
    exists = get_staff_by_nis(db, data["nis_no"])
    if exists:
        raise ValueError("NIS/No already exists")
    obj = models.Staff(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def update_staff(db: Session, obj: models.Staff, data: dict) -> models.Staff:
    for k, v in data.items():
        setattr(obj, k, v)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def delete_staff(db: Session, obj: models.Staff) -> None:
    db.delete(obj)
    db.commit()

def create_audit_log(db: Session, action: str, target: str, details: Optional[str] = None, formation_id: Optional[int] = None, office_id: Optional[int] = None, user_id: Optional[int] = None, username: Optional[str] = None) -> models.AuditLog:
    obj = models.AuditLog(action=action, target=target, details=details, formation_id=formation_id, office_id=office_id, user_id=user_id, username=username)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def list_audit_logs(db: Session, limit: int = 100, offset: int = 0, formation_id: Optional[int] = None, office_id: Optional[int] = None, actions: Optional[List[str]] = None) -> List[models.AuditLog]:
    stmt = select(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).offset(offset).limit(limit)
    if formation_id:
        stmt = stmt.where(models.AuditLog.formation_id == formation_id)
    if office_id:
        stmt = stmt.where(models.AuditLog.office_id == office_id)
    if actions:
        stmt = stmt.where(models.AuditLog.action.in_(actions))
    return list(db.scalars(stmt))

def get_all_descendant_ids(db: Session, root_id: int) -> list[int]:
    ids = {root_id}
    queue = [root_id]
    while queue:
        curr = queue.pop(0)
        children = db.scalars(select(models.Formation).where(models.Formation.parent_id == curr)).all()
        for c in children:
            if c.id not in ids:
                ids.add(c.id)
                queue.append(c.id)
    return list(ids)

def get_dashboard_stats(db: Session, formation_id: Optional[Union[int, list[int]]] = None):
    # Recursive ID resolution for Service Headquarters and Zonal Commands
    target_ids = []
    if formation_id:
        if isinstance(formation_id, list):
            # If list, assume strict filtering or we'd need to expand each
            target_ids = formation_id
        else:
            # If single ID, check if it's SHQ or Zonal Command and get descendants
            fmt = db.get(models.Formation, formation_id)
            if fmt and fmt.formation_type in ["Service Headquarters", "Zonal Command", "Directorate"]:
                target_ids = get_all_descendant_ids(db, formation_id)
            else:
                target_ids = [formation_id]

    staff_q = select(func.count(models.Staff.id)).where(models.Staff.exit_date.is_(None))
    office_q = select(func.count(distinct(models.Staff.office))).where(
            models.Staff.exit_date.is_(None),
            models.Staff.office.is_not(None),
            models.Staff.office != ""
        )
    rank_q = select(models.Staff.rank, func.count(models.Staff.id)).where(models.Staff.exit_date.is_(None)).group_by(models.Staff.rank)

    if target_ids:
        staff_q = staff_q.where(models.Staff.formation_id.in_(target_ids))
        office_q = office_q.where(models.Staff.formation_id.in_(target_ids))
        rank_q = rank_q.where(models.Staff.formation_id.in_(target_ids))

    total_staff = db.scalar(staff_q)
    total_offices = db.scalar(office_q)
    rank_rows = db.execute(rank_q).all()
    
    rank_counts = {}
    for rank, count in rank_rows:
        key = rank or ""
        rank_counts[key] = rank_counts.get(key, 0) + count
    return {
        "total_staff": total_staff,
        "total_offices": total_offices,
        "rank_counts": rank_counts,
    }

def list_offices(db: Session, formation_id: Optional[int] = None) -> List[str]:
    # Deprecated: returns distinct strings from Staff table
    stmt = select(distinct(models.Staff.office)).where(models.Staff.office.is_not(None)).order_by(models.Staff.office)
    if formation_id:
        stmt = stmt.where(models.Staff.formation_id == formation_id)
    return list(db.scalars(stmt))

def list_offices_model(db: Session, formation_id: Optional[Union[int, List[int]]] = None) -> List[models.Office]:
    stmt = select(models.Office).order_by(models.Office.name)
    if formation_id is not None:
        if isinstance(formation_id, list):
            stmt = stmt.where(models.Office.formation_id.in_(formation_id))
        else:
            stmt = stmt.where(models.Office.formation_id == formation_id)
    return list(db.scalars(stmt))

def get_office(db: Session, office_id: int) -> Optional[models.Office]:
    return db.get(models.Office, office_id)

def get_office_by_name(db: Session, name: str) -> Optional[models.Office]:
    return db.scalar(select(models.Office).where(func.lower(models.Office.name) == name.lower()))

def create_office(db: Session, name: str, formation_id: Optional[int] = None, office_type: Optional[str] = None, parent_id: Optional[int] = None) -> models.Office:
    # Check uniqueness within formation
    stmt = select(models.Office).where(
        func.lower(models.Office.name) == name.lower(),
        models.Office.formation_id == formation_id
    )
    existing = db.scalar(stmt)
    if existing:
        raise ValueError(f"Office '{name}' already exists in this formation")

    obj = models.Office(name=name, formation_id=formation_id, office_type=office_type, parent_id=parent_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def update_office(db: Session, office_id: int, name: str, office_type: Optional[str] = None, parent_id: Optional[int] = None) -> Optional[models.Office]:
    obj = db.get(models.Office, office_id)
    if obj:
        # Check uniqueness within formation (excluding self)
        stmt = select(models.Office).where(
            func.lower(models.Office.name) == name.lower(),
            models.Office.formation_id == obj.formation_id,
            models.Office.id != office_id
        )
        existing = db.scalar(stmt)
        if existing:
            raise ValueError(f"Office '{name}' already exists in this formation")

        if office_type == "Directorate":
             fmt = db.get(models.Formation, obj.formation_id)
             if not fmt or fmt.formation_type != "Directorate":
                 raise ValueError("Office type 'Directorate' can only be assigned in a Directorate formation")

        obj.name = name
        if office_type is not None:
            obj.office_type = office_type
        if parent_id is not None:
            obj.parent_id = parent_id
        db.add(obj)
        db.commit()
        db.refresh(obj)
    return obj

def delete_office(db: Session, office_id: int) -> bool:
    obj = db.get(models.Office, office_id)
    if obj:
        db.delete(obj)
        db.commit()
        return True
    return False

# Formation CRUD
def create_formation(db: Session, name: str, code: str, formation_type: Optional[str] = None, parent_id: Optional[int] = None) -> models.Formation:
    # Auto-parent Directorate to Service Headquarters
    if formation_type == "Directorate" and not parent_id:
        shq = db.execute(select(models.Formation).where(
            or_(
                models.Formation.formation_type == "Service Headquarters",
                models.Formation.code == "SHQ"
            )
        )).scalar_one_or_none()
        if shq:
            parent_id = shq.id
            
    obj = models.Formation(name=name, code=code, formation_type=formation_type, parent_id=parent_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)

    # Auto-create Sub-formation for Zonal Commands
    if formation_type == "Zonal Command":
        hq_name = f"{name} Headquarters"
        hq_code = f"{code}-HQ"
        
        # Check if already exists (idempotency)
        exists = db.scalar(select(models.Formation).where(models.Formation.code == hq_code))
        if not exists:
            hq = models.Formation(name=hq_name, code=hq_code, formation_type="Zonal Headquarters", parent_id=obj.id)
            db.add(hq)
            db.commit()

    return obj

def update_formation(db: Session, formation_id: int, name: str, formation_type: Optional[str] = None, parent_id: Optional[int] = None) -> Optional[models.Formation]:
    obj = db.get(models.Formation, formation_id)
    if obj:
        obj.name = name
        if formation_type is not None:
            obj.formation_type = formation_type
        if parent_id is not None:
            obj.parent_id = parent_id
        db.add(obj)
        db.commit()
        db.refresh(obj)
    return obj

def list_formations(db: Session) -> List[models.Formation]:
    return list(db.scalars(select(models.Formation).order_by(models.Formation.name)))

def get_formation(db: Session, formation_id: int) -> Optional[models.Formation]:
    return db.get(models.Formation, formation_id)

def get_pending_edit_requests(db: Session, formation_id: Optional[int] = None) -> List[models.StaffEditRequest]:
    stmt = select(models.StaffEditRequest).join(models.Staff).where(models.StaffEditRequest.status == "review_pending")
    if formation_id:
        stmt = stmt.where(models.Staff.formation_id == formation_id)
    return list(db.scalars(stmt.order_by(models.StaffEditRequest.created_at.asc())))

def get_edit_request(db: Session, request_id: int) -> Optional[models.StaffEditRequest]:
    return db.get(models.StaffEditRequest, request_id)

def resolve_edit_request(db: Session, request_id: int, status: str, reviewer: str) -> Optional[models.StaffEditRequest]:
    req = db.get(models.StaffEditRequest, request_id)
    if req:
        req.status = status
        req.reviewed_at = func.now()
        req.reviewed_by = reviewer
        db.add(req)
        db.commit()
        db.refresh(req)
    return req

def get_users_by_formation(db: Session, formation_id: int) -> List[models.User]:
    return list(db.scalars(select(models.User).where(models.User.formation_id == formation_id)))

def get_user(db: Session, user_id: int) -> Optional[models.User]:
    return db.get(models.User, user_id)

def delete_user(db: Session, user_id: int) -> bool:
    user = db.get(models.User, user_id)
    if user:
        db.delete(user)
        db.commit()
        return True
    return False

def update_user_password(db: Session, user_id: int, password_hash: str) -> Optional[models.User]:
    user = db.get(models.User, user_id)
    if user:
        user.password_hash = password_hash
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def get_custom_field_definitions(db: Session) -> List[models.CustomFieldDefinition]:
    return list(db.scalars(select(models.CustomFieldDefinition).order_by(models.CustomFieldDefinition.id)))

def create_custom_field_definition(db: Session, name: str, label: str, field_type: str = "text") -> models.CustomFieldDefinition:
    # Check if exists
    existing = db.scalar(select(models.CustomFieldDefinition).where(models.CustomFieldDefinition.name == name))
    if existing:
        raise ValueError(f"Field with name '{name}' already exists")
        
    obj = models.CustomFieldDefinition(name=name, label=label, field_type=field_type)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def delete_custom_field_definition(db: Session, field_id: int) -> bool:
    obj = db.get(models.CustomFieldDefinition, field_id)
    if obj:
        db.delete(obj)
        db.commit()
        return True
    return False

def create_notification(db: Session, message: str, user_id: Optional[int] = None, staff_id: Optional[int] = None, formation_id: Optional[int] = None, office_name: Optional[str] = None) -> models.Notification:
    # Handle deprecated fields for backward compatibility if needed, but prefer user_id/staff_id
    notif = models.Notification(
        message=message,
        user_id=user_id,
        staff_id=staff_id,
        formation_id=formation_id,
        office_name=office_name
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif

def get_user_notifications(db: Session, user_id: int, role: str, formation_id: Optional[int] = None, office_name: Optional[str] = None) -> List[models.Notification]:
    # Build query based on role
    # 1. Direct targeting via user_id (for User table) or staff_id (for Staff table)
    
    conditions = []
    
    if role in ("special_admin", "formation_admin"):
        conditions.append(models.Notification.user_id == user_id)
        if role == "formation_admin" and formation_id:
            # Also include formation-wide notifications (deprecated style but supported)
            conditions.append(models.Notification.formation_id == formation_id)
    else:
        # Staff table
        conditions.append(models.Notification.staff_id == user_id)
        if role == "office_admin" and office_name:
            # Also include office-wide notifications
            conditions.append(models.Notification.office_name == office_name)
            
    # Always include unread, limit read?
    # For now just get all, sorted by date
    stmt = select(models.Notification).where(or_(*conditions)).order_by(models.Notification.timestamp.desc())
    return list(db.scalars(stmt))

def mark_notification_read(db: Session, notif_id: int) -> bool:
    notif = db.get(models.Notification, notif_id)
    if notif:
        notif.is_read = True
        db.commit()
        return True
    return False

def broadcast_notification(db: Session, message: str, formation_id: int = None, office_id: int = None, role: str = None):
    """
    Send notification to specific groups of admins.
    - role="special_admin": All special admins
    - role="main_admin": All main admins
    - formation_id: Formation Admin of that formation
    - office_id: Office Admin of that office
    """
    # Notify Special Admins (User table)
    if role == "special_admin":
        users = db.scalars(select(models.User).where(models.User.role == "special_admin")).all()
        for u in users:
            create_notification(db, message, user_id=u.id)
            
    # Notify Main Admins (Staff table)
    if role == "main_admin":
        staffs = db.scalars(select(models.Staff).where(models.Staff.role == "main_admin")).all()
        for s in staffs:
            create_notification(db, message, staff_id=s.id)

    # Notify Formation Admins (User table)
    if formation_id:
        users = db.scalars(select(models.User).where(models.User.formation_id == formation_id, models.User.role == "formation_admin")).all()
        for u in users:
            create_notification(db, message, user_id=u.id)

    # Notify Office Admins (Staff table)
    if office_id:
        office_obj = db.get(models.Office, office_id)
        if office_obj:
            # Find staff who are office_admin in this office
            # Note: staff.office is a string name
            staffs = db.scalars(select(models.Staff).where(
                func.lower(models.Staff.office) == office_obj.name.lower(), 
                models.Staff.formation_id == office_obj.formation_id,
                models.Staff.role == "office_admin"
            )).all()
            for s in staffs:
                create_notification(db, message, staff_id=s.id)

def process_due_retirements(db: Session) -> int:
    """
    Check for staff due for retirement (exit_date <= today) who are not yet exited.
    Update them and notify admins.
    Returns count of processed retirements.
    """
    today = date.today()
    
    # Find active staff (exit_mode is NULL) where exit_date <= today
    stmt = select(models.Staff).where(
        models.Staff.exit_mode.is_(None),
        models.Staff.exit_date.is_not(None),
        models.Staff.exit_date <= today
    )
    staff_due = db.scalars(stmt).all()
    
    count = 0
    for staff in staff_due:
        # Skip if CGI (exempt)
        if staff.rank == "CGI":
            continue
            
        # Process Retirement
        staff.exit_mode = "Retired"
        staff.allow_login = 0 # Revoke access
        
        # Notify Admins
        msg = f"Staff Retired: {staff.nis_no} ({staff.rank}) - {staff.surname} {staff.other_names}"
        
        # 1. Special Admin
        broadcast_notification(db, msg, role="special_admin")
        
        # 2. Formation Admin
        broadcast_notification(db, msg, formation_id=staff.formation_id)
        
        # 3. Main Admin
        broadcast_notification(db, msg, role="main_admin")
        
        # 4. Office Admin
        if staff.office:
            # Resolve office ID
            off_obj = db.scalar(select(models.Office).where(
                func.lower(models.Office.name) == staff.office.lower(),
                models.Office.formation_id == staff.formation_id
            ))
            if off_obj:
                broadcast_notification(db, msg, office_id=off_obj.id)
        
        count += 1
        
    if count > 0:
        db.commit()
        
    return count

