"""Normalize written date separators without inventing missing components."""
import re
from datetime import date


def normalize_sample_date(value):
    raw=str(value or '').strip()
    full=re.fullmatch(r'(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{2}|\d{4})',raw)
    if full:
        month,day,year=map(int,full.groups())
        year=year+2000 if year<100 else year
        try:
            parsed=date(year,month,day)
        except ValueError:
            return raw
        return f'{parsed.month:02d}/{parsed.day:02d}/{parsed.year:04d}'
    partial=re.fullmatch(r'(\d{1,2})\s*[/.-]\s*(\d{1,4})',raw)
    if partial:
        return '/'.join(partial.groups())
    return raw


def same_sample_date(left,right):
    return normalize_sample_date(left)==normalize_sample_date(right)
