from typing import Optional, Any, Dict
from datetime import date

def to_dict_state(obj) -> Dict[str, Any]:
    if not obj:
        return None
    return {"id": obj.id, "name": obj.name}

def to_dict_lga(obj) -> Dict[str, Any]:
    if not obj:
        return None
    return {"id": obj.id, "name": obj.name, "state_id": obj.state_id}

def to_dict_office(obj) -> Dict[str, Any]:
    return {"id": obj.id, "name": obj.name}

def to_dict_organization_simple(obj) -> Dict[str, Any]:
    if not obj: return None
    return {"id": obj.id, "name": obj.name, "code": obj.code}

def to_dict_staff(obj) -> Dict[str, Any]:
    return {
        "id": obj.id,
        "nis_no": obj.nis_no,
        "surname": obj.surname,
        "other_names": obj.other_names,
        "rank": obj.rank,
        "gender": obj.gender,
        "organization": to_dict_organization_simple(obj.organization),
        "dofa": obj.dofa.isoformat() if obj.dofa else None,
        "dopa": obj.dopa.isoformat() if obj.dopa else None,
        "dopp": obj.dopp.isoformat() if obj.dopp else None,
        "dob": obj.dob.isoformat() if obj.dob else None,
        "home_town": obj.home_town,
        "qualification": obj.qualification,
        "phone_no": obj.phone_no,
        "next_of_kin": obj.next_of_kin,
        "nok_phone": obj.nok_phone,
        "office": obj.office,
        "email": obj.email,
        "remark": obj.remark,
        "state": to_dict_state(obj.state),
        "lga": to_dict_lga(obj.lga),
        "exit_date": obj.exit_date.isoformat() if obj.exit_date else None,
        "exit_mode": obj.exit_mode,
        "out_request_status": obj.out_request_status,
        "out_request_date": obj.out_request_date.isoformat() if obj.out_request_date else None,
        "out_request_reason": obj.out_request_reason,
        "role": obj.role,
        "allow_edit_rank": bool(getattr(obj, "allow_edit_rank", 0)),
        "allow_edit_dopp": bool(getattr(obj, "allow_edit_dopp", 0)),
    }

def to_dict_leave(obj) -> Dict[str, Any]:
    return {
        "id": obj.id,
        "staff_id": obj.staff_id,
        "start_date": obj.start_date.isoformat() if obj.start_date else None,
        "end_date": obj.end_date.isoformat() if obj.end_date else None,
        "leave_type": obj.leave_type,
        "reason": obj.reason,
        "status": obj.status,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "staff_name": f"{obj.staff.surname} {obj.staff.other_names}" if obj.staff else "Unknown"
    }

def to_dict_audit_log(obj) -> Dict[str, Any]:
    return {
        "id": obj.id,
        "action": obj.action,
        "target": obj.target,
        "timestamp": obj.timestamp.isoformat() if obj.timestamp else None,
        "details": obj.details,
    }
