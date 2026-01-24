from typing import Optional, List, Union, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, case, func, distinct
from . import models

# Rank order mapping (Highest to Lowest)
RANK_ORDER = [
    "DCG", "ACG", "CIS", "DCI", "ACI", "CSI", "SI", "DSI",
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
    state_id: Optional[int] = None,
    lga_id: Optional[int] = None,
    rank: Optional[str] = None,
    office: Optional[str] = None,
    completeness: Optional[str] = None,
    status: Optional[str] = "active",
    dopp_order: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    exit_from=None,
    exit_to=None,
    dopa_from=None,
    dopa_to=None,
    formation_id: Optional[int] = None,
    include_count: bool = False
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
        stmt = stmt.where(models.Staff.state_id == state_id)
    if lga_id is not None:
        stmt = stmt.where(models.Staff.lga_id == lga_id)
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
        stmt = stmt.where(models.Staff.formation_id == formation_id)
    
    if completeness == "completed":
        # Criteria: Must have State, LGA, and Office
        stmt = stmt.where(
            models.Staff.state_id.is_not(None),
            models.Staff.lga_id.is_not(None),
            models.Staff.office.is_not(None),
            models.Staff.office != ""
        )
    elif completeness == "incomplete":
        # Criteria: Missing ANY of State, LGA, or Office
        stmt = stmt.where(
            or_(
                models.Staff.state_id.is_(None),
                models.Staff.lga_id.is_(None),
                models.Staff.office.is_(None),
                models.Staff.office == ""
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

def create_audit_log(db: Session, action: str, target: str, details: Optional[str] = None, formation_id: Optional[int] = None) -> models.AuditLog:
    obj = models.AuditLog(action=action, target=target, details=details, formation_id=formation_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def list_audit_logs(db: Session, limit: int = 100, offset: int = 0, formation_id: Optional[int] = None) -> List[models.AuditLog]:
    stmt = select(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).offset(offset).limit(limit)
    if formation_id:
        stmt = stmt.where(models.AuditLog.formation_id == formation_id)
    return list(db.scalars(stmt))

def get_dashboard_stats(db: Session, formation_id: Optional[int] = None):
    staff_q = select(func.count(models.Staff.id)).where(models.Staff.exit_date.is_(None))
    office_q = select(func.count(distinct(models.Staff.office))).where(
            models.Staff.exit_date.is_(None),
            models.Staff.office.is_not(None),
            models.Staff.office != ""
        )
    rank_q = select(models.Staff.rank, func.count(models.Staff.id)).where(models.Staff.exit_date.is_(None)).group_by(models.Staff.rank)

    if formation_id:
        staff_q = staff_q.where(models.Staff.formation_id == formation_id)
        office_q = office_q.where(models.Staff.formation_id == formation_id)
        rank_q = rank_q.where(models.Staff.formation_id == formation_id)

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

def list_offices_model(db: Session, formation_id: Optional[int] = None) -> List[models.Office]:
    stmt = select(models.Office).order_by(models.Office.name)
    if formation_id:
        stmt = stmt.where(models.Office.formation_id == formation_id)
    return list(db.scalars(stmt))

def create_office(db: Session, name: str, formation_id: Optional[int] = None) -> models.Office:
    obj = models.Office(name=name, formation_id=formation_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def update_office(db: Session, office_id: int, name: str) -> Optional[models.Office]:
    obj = db.get(models.Office, office_id)
    if obj:
        obj.name = name
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
def create_formation(db: Session, name: str, code: str, description: Optional[str] = None) -> models.Formation:
    obj = models.Formation(name=name, code=code, description=description)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def update_formation(db: Session, formation_id: int, name: str, description: Optional[str] = None) -> Optional[models.Formation]:
    obj = db.get(models.Formation, formation_id)
    if obj:
        obj.name = name
        if description is not None:
            obj.description = description
        db.add(obj)
        db.commit()
        db.refresh(obj)
    return obj

def list_formations(db: Session) -> List[models.Formation]:
    return list(db.scalars(select(models.Formation).order_by(models.Formation.name)))

def get_formation(db: Session, formation_id: int) -> Optional[models.Formation]:
    return db.get(models.Formation, formation_id)

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
