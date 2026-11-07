"""Add date display formatting to the comparison; never rewrite OCR targets."""
import csv
import json
from pathlib import Path
from date_formats import format_sample_date

root=Path(__file__).resolve().parent
run=sorted(p for p in (root/'training-expanded').iterdir() if (p/'prediction-comparison.json').exists())[-1]
rows=json.loads((run/'prediction-comparison.json').read_text())
for row in rows:
    if row['field']!='date_sampled':continue
    for column in ['expected','original','trained']:
        parsed=format_sample_date(row[column])
        row[column+'_formatted']=parsed['formatted']
        row[column+'_date_status']=parsed['status']
        row[column+'_date_assumption']=parsed['assumption'] or ''
fields=list(dict.fromkeys(key for row in rows for key in row))
with (run/'formatted-date-comparison.csv').open('w',newline='',encoding='utf-8-sig') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
print(run/'formatted-date-comparison.csv')
for row in rows:
    if row['field']=='date_sampled':print(row['trained'],'->',row['trained_formatted'] or '[needs review]')
