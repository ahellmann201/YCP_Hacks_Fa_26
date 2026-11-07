"""Format OCR date output; retain raw text and make partial-date policy explicit."""
import re
from datetime import date


def format_sample_date(value, two_part='month_year', century=2000):
    """Two-part dates follow the user's month/year policy, with an assumption flag.

    Does not split merged digits, infer missing digits, or change OCR letters.
    Two-digit years use the explicitly configured century (default 2000).
    """
    raw=str(value or '').strip()
    result={'raw':raw,'formatted':'','precision':None,'status':'needs_review',
            'assumption':None}
    if not raw:
        result['status']='blank'
        return result
    parts=re.fullmatch(r'\s*(\d{1,2})\s*[/\.\-]\s*(\d{1,4})\s*(?:[/\.\-]\s*(\d{2}|\d{4}))?\s*',raw)
    if not parts:return result
    month,middle,last=parts.groups()
    month=int(month)
    if not 1<=month<=12:return result
    if last is not None:
        day=int(middle);year_text=last
        precision='day'
    else:
        if two_part!='month_year':return result
        if len(middle) not in {2,4}:return result
        year_text=middle;day=1;precision='month'
        if len(middle)==2:
            result['assumption']='Two-part value interpreted as month/year by configured policy; it could be month/day.'
    year=int(year_text)+(century if len(year_text)==2 else 0)
    try:date(year,month,day)
    except ValueError:return result
    result.update(formatted=f'{month:02d}/{day:02d}/{year:04d}' if precision=='day' else f'{month:02d}/{year:04d}',
                  precision=precision,status='formatted')
    return result
