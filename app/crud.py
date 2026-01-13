from typing import Optional, List
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
) -> List[models.Staff]:
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
    
    if dopp_order in ("asc", "desc"):
        stmt = select(models.Staff).order_by(
            models.Staff.dopp.asc() if dopp_order == "asc" else models.Staff.dopp.desc(),
            models.Staff.nis_no
        ).offset(offset).limit(limit)
    else:
        stmt = select(models.Staff).order_by(
            rank_sort, 
            models.Staff.dopa.asc(),
            models.Staff.nis_no
        ).offset(offset).limit(limit)
    
    if status == "active":
        stmt = stmt.where(models.Staff.exit_date.is_(None))
    elif status == "exited":
        stmt = stmt.where(models.Staff.exit_date.is_not(None))

    if state_id is not None:
        stmt = stmt.where(models.Staff.state_id == state_id)
    if lga_id is not None:
        stmt = stmt.where(models.Staff.lga_id == lga_id)
    if rank:
        stmt = stmt.where(models.Staff.rank == rank)
    if office:
        stmt = stmt.where(models.Staff.office == office)
    
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
    return list(db.scalars(stmt))

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

def create_audit_log(db: Session, action: str, target: str, details: Optional[str] = None) -> models.AuditLog:
    obj = models.AuditLog(action=action, target=target, details=details)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def list_audit_logs(db: Session, limit: int = 100, offset: int = 0) -> List[models.AuditLog]:
    return list(db.scalars(select(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).offset(offset).limit(limit)))

def get_dashboard_stats(db: Session):
    total_staff = db.scalar(
        select(func.count(models.Staff.id)).where(models.Staff.exit_date.is_(None))
    )
    # Count distinct offices, ignoring None or empty strings
    # Note: SQLite might behave differently with NULLs in count(distinct), but let's filter explicitly
    total_offices = db.scalar(
        select(func.count(distinct(models.Staff.office)))
        .where(
            models.Staff.exit_date.is_(None),
            models.Staff.office.is_not(None),
            models.Staff.office != ""
        )
    )
    return {
        "total_staff": total_staff,
        "total_offices": total_offices
    }

def list_offices(db: Session) -> List[str]:
    # Deprecated: returns distinct strings from Staff table
    return list(db.scalars(select(distinct(models.Staff.office)).where(models.Staff.office.is_not(None)).order_by(models.Staff.office)))

def list_offices_model(db: Session) -> List[models.Office]:
    return list(db.scalars(select(models.Office).order_by(models.Office.name)))

def create_office(db: Session, name: str) -> models.Office:
    obj = models.Office(name=name)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def update_office(db: Session, office_id: int, name: str) -> Optional[models.Office]:
    obj = db.get(models.Office, office_id)
    if obj:
        old_name = obj.name
        obj.name = name
        # Update staff records
        db.execute(
            models.Staff.__table__.update().where(models.Staff.office == old_name).values(office=name)
        )
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

def create_leave(db: Session, data: dict) -> models.Leave:
    obj = models.Leave(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def get_leave(db: Session, leave_id: int) -> Optional[models.Leave]:
    return db.get(models.Leave, leave_id)

def list_leaves(
    db: Session,
    staff_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[models.Leave]:
    stmt = select(models.Leave).order_by(models.Leave.created_at.desc())
    if staff_id:
        stmt = stmt.where(models.Leave.staff_id == staff_id)
    if status:
        stmt = stmt.where(models.Leave.status == status)
    
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))

def update_leave_status(db: Session, leave_id: int, status: str) -> Optional[models.Leave]:
    leave = get_leave(db, leave_id)
    if leave:
        leave.status = status
        db.commit()
        db.refresh(leave)
    return leave
