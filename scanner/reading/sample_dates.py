"""Normalize written date separators without inventing missing components."""
import re
from datetime import date


def normalize_sample_date(value):
    raw=str(value or '').strip()
    full=re.fullmatch(r'(\d{1,2})\s*[/+.-]\s*(\d{1,2})\s*[/+.-]\s*(\d{2}|\d{4})',raw)
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


def sampled_date_issue(value, received):
    raw=str(value or '').strip()
    if not raw:
        return ''
    match=re.fullmatch(r'(\d{1,2})\s*[/+.-]\s*(\d{1,2})\s*[/+.-]\s*(\d{2}|\d{4})',raw)
    if not match:
        return ''  # Partial/ambiguous dates keep their existing review policy.
    month,day,year=map(int,match.groups());year=year+2000 if year<100 else year
    try:
        sampled=date(year,month,day)
    except ValueError:
        return 'Date Sampled is not a valid calendar date. Check the crop.'
    try:
        received_date=date.fromisoformat(received)
    except ValueError:
        return ''
    if sampled>received_date:
        return 'Date Sampled is after Date Received. Check the year/digits or correct Date Received.'
    return ''


def recover_collapsed_date(value):
    """Insert a slash that the reader dropped when the leading digits cannot be a month."""
    raw=str(value or '').strip()
    three=re.fullmatch(r'(\d)(\d{2})',raw)
    if three and int(three.group(1)+three.group(2)[0])>12 and 1<=int(three.group(2))<=31:
        return f'{three.group(1)}/{three.group(2)}'
    mixed=re.fullmatch(r'(\d)(\d{2})\s*[/+.-]\s*(\d{2}|\d{4})',raw)
    if mixed and int(mixed.group(1)+mixed.group(2)[0])>12 and 1<=int(mixed.group(2))<=31:
        return f'{mixed.group(1)}/{mixed.group(2)}/{mixed.group(3)}'
    slash_read_as_one=re.fullmatch(r'([2-9])1(\d{2})(\d{2})',raw)
    if slash_read_as_one and 1<=int(slash_read_as_one.group(2))<=31:
        return f'{slash_read_as_one.group(1)}/{slash_read_as_one.group(2)}/{slash_read_as_one.group(3)}'
    return raw


def extract_written_date(value):
    raw=recover_collapsed_date(value)
    if not re.fullmatch(r'\d{1,4}\s*[/+.-]\s*\d{1,4}(?:\s*[/+.-]\s*\d{1,4})?',raw):
        return ''
    compact=re.sub(r'\s+','',raw)
    if any(int(part)==0 for part in re.split(r'[/+.-]',compact)):
        return ''
    return compact
