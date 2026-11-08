"""Validate and package only the wider replacement keys after an adhesion failure."""
from pathlib import Path
import hashlib, json, re, shutil, zipfile
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parent
out=root/'final files'
name='04_WIDE_T_KEY_ZERO_GAP_P1P_PLA'
with zipfile.ZipFile(out/(name+'.gcode.3mf')) as z:
    cfg=json.loads(z.read('Metadata/project_settings.config'))
    assert cfg['printer_model']=='Bambu Lab P1P'
    assert cfg['nozzle_diameter']==['0.4'] and cfg['filament_type']==['PLA']
    assert cfg['curr_bed_type']=='Textured PEI Plate'
    assert cfg['brim_type']=='outer_only' and cfg['brim_width']=='8'
    assert cfg['brim_object_gap']=='0' and cfg['elefant_foot_compensation']=='0'
    plate=json.loads(z.read('Metadata/plate_1.json'))
    assert len(plate['bbox_objects'])==2
    assert all(o['name']=='locking_key' for o in plate['bbox_objects'])
    info=ET.fromstring(z.read('Metadata/slice_info.config'))
    meta={v.attrib['key']:v.attrib['value'] for v in info.findall('./plate/metadata')}
    assert meta['outside']=='false' and meta['support_used']=='false'
    raw=z.read('Metadata/plate_1.gcode')
    assert hashlib.md5(raw).hexdigest().upper()==z.read('Metadata/plate_1.gcode.md5').decode().strip().upper()
    assert len(re.findall(rb'^; FEATURE: Brim\r?$',raw,re.M))==2
    (out/(name+'.gcode')).write_bytes(raw)
    (out/(name+'_plate.png')).write_bytes(z.read('Metadata/plate_1.png'))
report={'objects':2,'estimated_seconds':int(meta['prediction']),
        'filament_g':float(meta['weight']),'brim_width_mm':8,'brim_gap_mm':0,
        'elephant_foot_compensation_mm':0,'grip_width_mm':16,'stem_width_mm':3.4,
        'gcode_md5':hashlib.md5(raw).hexdigest(),
        'status':'Digitally checked; physical adhesion and locking fit need testing.'}
(out/'04_WIDE_T_KEY_validation.json').write_text(json.dumps(report,indent=2))
source=(root/'three_tube_gear_scanner.scad').read_text()
(out/'04_WIDE_T_KEY.scad').write_text(source.replace('part = "assembly";', 'part = "locking_key";',1))
notice='''CURRENT RETRY - WIDER T-SHAPED LOCKING KEY
The original T detached while its brim stayed on the plate. Keep the other
successful fit-test pieces. Next print ONLY:
04_WIDE_T_KEY_ZERO_GAP_P1P_PLA.gcode.3mf

Two replacement keys. Estimated 21 min 52 sec, 1.82 g PLA, P1P / 0.4 mm /
Generic PLA / Textured PEI Plate. No printing has been started remotely.
Grip widened from 9 to 16 mm; mating stem remains 3.4 mm wide. Overall length
27 mm and maximum height 4.2 mm are unchanged. Tapered grip corners are shaped
to clear the nearby gears. Do not scale the whole model in Studio.

8 mm outer brim, ZERO brim-object gap, elephant-foot compensation off for
this retry, first-layer walls 15 mm/s, first-layer infill 20 mm/s, later
outer walls 25 mm/s and inner walls 30 mm/s, reduced acceleration. Part fan
off for first 3 layers, then normal cooling with a 15-second layer-time target.

Open this specifically named new file; an old project open in Studio does
not update itself. Check Preview shows two wider keys with surrounding brims.
Use the prepared slice. If reslicing, keep the ZERO GAP custom process.
Check the actual plate is Textured PEI and run bed leveling. Watch the first
layer. Stop if a key detaches; continuing will only deposit tangled plastic.

Let the plate cool before removal. The brim now attaches more firmly. Trim
it flush from the stem and underside before the fit test, without cutting
into the 3.4 mm stem. Do not force the key into the slot. Test on the short
leg and small square plate you already printed. Report whether it stays
attached through printing and then locks the joint without cracking/rattle.

The older 00 fit-test and 01 base sliced files still contain the narrower
key. Do not start the full base print yet: verify this revised key first,
then update the complete base print to use the successful key/settings.
The source SCADs, unsliced geometry and locking_key.stl now use the wider grip.
Gear-and-washer geometry and its sliced file are unchanged.

This is a targeted prototype retry, not a guarantee of successful adhesion.
--- END CURRENT RETRY NOTE ---

'''
if (out/'01_BASE_WIDE_KEYS_BRIM_P1P_PLA.gcode.3mf').exists():
    notice='''CURRENT PRINT ORDER - WIDE KEY REVISION
The user reports the wide-key retry printed successfully. Check that a
trimmed key also holds the existing test joint firmly before the full print.
NEXT: 01_BASE_WIDE_KEYS_BRIM_P1P_PLA.gcode.3mf
Then: 02_gears_and_washers_P1P_PLA.gcode.3mf

The base slice includes six 16 mm grip keys with the unchanged 3.4 mm stem,
plus the base, four legs and two motor brackets. It uses the same 8 mm
zero-gap brim and slow first layer as the successful key retry. Keys keep
slow upper-layer speeds; larger parts use normal speeds. Trim brims
flush after cooling, especially around pegs and key stems. Keep 100% scale.
The two previously printed keys can be spares. The 04 file remains available
for printing replacement keys only; the older 00 fit slice has narrow keys.
See PRINT_AND_ASSEMBLY.txt for the updated base estimate and assembly steps.
No printer has been started remotely. Loaded assembly fit remains untested.
--- END CURRENT RETRY NOTE ---

'''
(out/'04_RETRY_INSTRUCTIONS.txt').write_text(notice)
guide=out/'PRINT_AND_ASSEMBLY.txt'
previous=guide.read_text(encoding='utf-8')
if '--- END CURRENT RETRY NOTE ---' in previous:
    previous=previous.split('--- END CURRENT RETRY NOTE ---',1)[1].lstrip()
guide.write_text(notice+previous,encoding='utf-8')
archive=root/'superseded_key_retries'
archive.mkdir(exist_ok=True)
for ext in ('.gcode.3mf','.gcode'):
    old=out/('04_T_KEY_RETRY_ZERO_GAP_P1P_PLA'+ext)
    target=archive/old.name
    if old.exists():
        assert not target.exists(), 'Refusing to overwrite an archived retry'
        shutil.move(str(old),str(target))
with zipfile.ZipFile(root/'final_print_files.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(out.rglob('*')):
        if f.is_file(): z.write(f,f.relative_to(out))
print(json.dumps(report,indent=2))
