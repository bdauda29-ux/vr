
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
    # Since we don't know if 'user_id' param is from User or Staff table without context, 
    # we assume the caller knows. But wait, main.py passes user['id'].
    # If role is special/formation_admin, it's User table.
    # If role is main/office_admin, it's Staff table.
    
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
    
    # Staff who have exit_date set, are <= today, and exit_mode is NULL (not yet processed)
    # OR we can assume if exit_mode is NULL they are active.
    # We should also check those who DON'T have exit_date but should? 
    # The requirement says "when retirement date reaches".
    # Assuming exit_date is calculated/stored. If not, we rely on DOB/DOFA.
    # But usually exit_date is set. If not, we might need to calculate it on the fly?
    # Let's assume exit_date is authoritative if present.
    
    # Find active staff (exit_mode is NULL) where exit_date <= today
    stmt = select(models.Staff).where(
        models.Staff.exit_mode.is_(None),
        models.Staff.exit_date.is_not(None),
        models.Staff.exit_date <= today
    )
    staff_due = db.scalars(stmt).all()
    
    count = 0
    for staff in staff_due:
        # Skip if CGI (exempt) - though exit_date shouldn't be set for them theoretically, or set to future.
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
