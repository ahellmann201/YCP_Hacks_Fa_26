"""Remove known printed headings; conservatively recognize visually empty crops."""
import re


def keep_complete_page_reading(page, crop):
    """Keep a full-label number when the field crop only captured part of it."""
    page = str(page or '').strip()
    crop = str(crop or '').strip()
    if page.isdigit() and crop.isdigit() and len(page) > len(crop) and (
        page.startswith(crop) or page.endswith(crop)
    ):
        return page
    return crop


def keep_added_character(broad, tight):
    """Use the tight crop when it is the broad reading plus one letter or digit."""
    broad = str(broad or '')
    tight = str(tight or '')
    if not broad or len(tight) != len(broad) + 1:
        return broad
    for index, character in enumerate(tight):
        if character.isalnum() and tight[:index] + tight[index + 1:] == broad:
            return tight
    return broad


def prefer_explicit_rn(page, crop):
    """Keep a printed RN line when it is UP plus the digits the crop misread."""
    compact = re.sub(r'\s+', '', str(page or ''))
    crop = str(crop or '').strip()
    if re.fullmatch(r'UP\d{3,}', compact, re.I) and compact.upper() != crop.upper():
        return 'UP' + compact[2:]
    return crop


def separate_number_code(value):
    """Put the space back in a code such as 420NPF."""
    value = str(value or '').strip()
    match = re.fullmatch(r'(\d{1,4})([A-Za-z]{2,5})', value)
    if match:
        return f'{match.group(1)} {match.group(2)}'
    return value


def restore_page_word_gap(page, crop):
    """Keep the page's word break when the crop glued the last word to extra letters."""
    crop = str(crop or '').strip()
    if ' ' in crop:
        return crop
    parts = str(page or '').split()
    if len(parts) < 2:
        return crop
    suffix = parts[-1]
    if len(suffix) < 3 or not suffix.isalpha() or not crop.upper().endswith(suffix.upper()):
        return crop
    prefix = crop[:len(crop) - len(suffix)]
    if prefix.isalpha() and 1 <= len(prefix) <= 4:
        return f'{prefix} {crop[-len(suffix):]}'
    return crop


def repair_lone_i(value):
    """A lone I before a digit is the digit 1, as in AEROSHELL 14."""
    return re.sub(r'(?<![A-Za-z])I(?=\d)', '1', str(value or ''))


def strip_heading(value, field, kind):
    value=str(value or '').strip()
    patterns={
        'date_sampled':r'(?:date(?:\s*sampled)?|sampled)',
        'serial_number':r'SN',
    }
    if kind=='large':
        patterns.update(machine=r'(?:equip(?:ment)?\s*[i1l][d0o])',
                        component=r'(?:(?:sample|sampl|ample|mple|ple|le)\s*point|point)',
                        reference_lube=r'(?:ref(?:erence)?\s*lube|lube)')
    else:
        patterns['machine']=r'RN'
    pattern=patterns.get(field)
    if pattern:
        value=re.sub(r'^\s*'+pattern+r'(?=\s|[:;|._-]|$)\s*[:;|._-]*\s*','',value,flags=re.I)
    value=value.strip(' \t:;|')
    return '' if re.fullmatch(r'[-_=—–\s]+',value) else value


def visually_empty(crop):
    import cv2
    import numpy as np
    if crop.shape[0]<30 or crop.shape[1]<80:
        return False
    gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
    background=float(np.median(gray))
    if background<170:
        return False
    ink=(gray<background-12).astype('uint8')
    ignored=np.zeros(gray.shape,dtype=bool)
    count,labels,stats,_=cv2.connectedComponentsWithStats(ink,8)
    for n in range(1,count):
        _,_,width,height,_=stats[n]
        if width>=gray.shape[1]*.7 and height<=max(2,int(gray.shape[0]*.02)):
            ink[labels==n]=0  # A thin printed underline, not a tall text component.
            ignored[labels==n]=True
    remaining=gray[~ignored]
    return int(ink.sum())==0 and remaining.size>0 and int(remaining.max())-int(remaining.min())<=2
