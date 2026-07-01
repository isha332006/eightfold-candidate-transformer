"""Step: match/cluster RawRecords from different sources into one cluster
per real candidate, before merging field values.

Match strategy (in priority order):
  1. Two records sharing a normalized email -> same person.
  2. Two records with no email collision but identical normalized full name,
     where at least one of them has no email at all -> same person (weak
     match, used to stitch e.g. a resume with no email onto a CSV row).
A record that matches nothing becomes its own single-record cluster.
"""
from .normalize import normalize_email, normalize_name


class _UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _record_emails(rec):
    out = set()
    for fv in rec.fields.get("email_raw", []):
        norm = normalize_email(fv.value)
        if norm:
            out.add(norm)
    return out


def _record_name(rec):
    vals = rec.fields.get("full_name", [])
    if not vals:
        return None
    norm = normalize_name(vals[0].value)
    return norm.lower() if norm else None


def cluster_records(records: list) -> list:
    n = len(records)
    uf = _UnionFind(n)

    emails_by_idx = [_record_emails(r) for r in records]
    names_by_idx = [_record_name(r) for r in records]

    # Pass 1: union on shared email
    email_to_first = {}
    for i, emails in enumerate(emails_by_idx):
        for e in emails:
            if e in email_to_first:
                uf.union(email_to_first[e], i)
            else:
                email_to_first[e] = i

    # Pass 2: union on shared name where at least one side has no email
    name_to_first = {}
    for i, name in enumerate(names_by_idx):
        if not name:
            continue
        if name in name_to_first:
            j = name_to_first[name]
            if not emails_by_idx[i] or not emails_by_idx[j]:
                uf.union(j, i)
            elif emails_by_idx[i] & emails_by_idx[j]:
                uf.union(j, i)  # already covered, harmless
        else:
            name_to_first[name] = i

    clusters = {}
    for i in range(n):
        root = uf.find(i)
        clusters.setdefault(root, []).append(records[i])
    return list(clusters.values())
