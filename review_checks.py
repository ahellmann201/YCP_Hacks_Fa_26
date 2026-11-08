"""Conservative review hints, not a calibrated probability of correctness."""
import math


def field_checks(fields, kind, result):
    keys = ['sample_id', 'date_sampled', 'machine', 'component']
    keys += ['serial_number'] if kind == 'small' else ['reference_lube'] if kind == 'large' else ['serial_number', 'reference_lube']
    checks = {}
    for key in keys:
        reasons = []
        value = str(fields.get(key) or '').strip()
        if not value:
            reasons.append('Missing reading — check whether this field is blank.')
        if kind not in {'small', 'large'}:
            reasons.append('Label type needs checking.')
        if len(result.get('alternatives', {}).get(key, [])) > 1:
            reasons.append('Photos gave conflicting readings.')
        if key == 'date_sampled':
            reasons.append('Verify the handwritten date and any missing parts.')
        elif key == 'component' and kind == 'small':
            reasons.append('Verify the circled number and GS/NGS.')
        elif key != 'sample_id' and value:
            scores = []
            for image in result.get('images', []):
                observed = str(image.get('fields', {}).get(key) or '').strip()
                score = image.get('field_scores', {}).get(key)
                if observed.casefold() == value.casefold() and isinstance(score, (int, float)) and math.isfinite(score):
                    scores.append(score)
            if not scores:
                reasons.append('No confidence information — verify this reading.')
            elif min(scores) < .95:
                reasons.append('OCR confidence is below the review threshold.')
        for image in result.get('images', []):
            for warning in image.get('warnings', []):
                if warning.startswith(key+':') and warning not in reasons:
                    reasons.append(warning)
        checks[key] = reasons
    return checks
