"""Assembles nested response schemas from ORM rows (Patient + its
timeline/report children, etc.) so routers stay thin."""

from app import models, schemas


def patient_to_schema(p: models.Patient) -> schemas.Patient:
    return schemas.Patient(
        id=p.id,
        patient_code=p.patient_code,
        name=p.name,
        age=p.age,
        gender=p.gender,
        phone=p.phone,
        email=p.email,
        hospital=p.hospital,
        stage=p.stage,
        tumor_size_mm=p.tumor_size_mm,
        er_status=p.er_status,
        pr_status=p.pr_status,
        her2_status=p.her2_status,
        ki67=p.ki67,
        grade=p.grade,
        nodes_involved=p.nodes_involved,
        current_treatment=p.current_treatment,
        status=p.status,
        risk=p.risk,
        survival_probability=p.survival_probability,
        last_updated=p.last_updated,
        diagnosed_on=p.diagnosed_on,
        twin_status=p.twin_status,
        history=p.history or [],
        notes=p.notes or "",
        timeline=[
            schemas.TimelineEvent(date=t.date, title=t.title, detail=t.detail, kind=t.kind)
            for t in sorted(p.timeline, key=lambda t: t.date, reverse=True)
        ],
        reports=[
            schemas.PatientReportRef(name=r.name, type=r.type, date=r.date, size=r.size)
            for r in p.reports
        ],
        comorbidities=p.comorbidities or [],
        allergies=p.allergies or [],
        current_medications=p.current_medications or [],
        previous_treatments=p.previous_treatments or [],
        family_history=p.family_history or "",
        smoking_status=p.smoking_status or "Unknown",
        alcohol_use=p.alcohol_use or "Unknown",
        surgical_history=p.surgical_history or [],
    )
