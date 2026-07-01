"""Extract from a recruiter CSV export: name,email,phone,current_company,title"""
import csv

from ..types import RawRecord


def extract_recruiter_csv(path: str) -> list:
    records = []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return records  # empty/garbage file -> no records, don't crash
            # normalize header names defensively (case/whitespace)
            field_map = {h.strip().lower(): h for h in reader.fieldnames}

            def get(row, key):
                h = field_map.get(key)
                return row.get(h, "").strip() if h else ""

            for row in reader:
                rec = RawRecord(source="recruiter_csv")
                name = get(row, "name")
                email = get(row, "email")
                phone = get(row, "phone")
                company = get(row, "current_company")
                title = get(row, "title")
                if not any([name, email, phone, company, title]):
                    continue
                rec.add("full_name", name, "csv_column:name", raw=name)
                rec.add("email_raw", email, "csv_column:email", raw=email)
                rec.add("phone_raw", phone, "csv_column:phone", raw=phone)
                rec.add("current_company", company, "csv_column:current_company", raw=company)
                rec.add("current_title", title, "csv_column:title", raw=title)
                records.append(rec)
    except (FileNotFoundError, UnicodeDecodeError, csv.Error):
        return []  # malformed/missing source: degrade gracefully
    return records
