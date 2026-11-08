"""Keep slow key overrides while using normal speeds for the larger base parts."""
from pathlib import Path
import json, zipfile
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parent
profiles=root/'print_parts'/'p1p_profiles'
normal=json.loads((profiles/'process.json').read_text())
slow=json.loads((profiles/'process_key.json').read_text())
for key in ('brim_type','brim_width','brim_object_gap','elefant_foot_compensation',
            'initial_layer_speed','initial_layer_infill_speed','initial_layer_acceleration'):
    normal[key]=slow[key]
normal['name']=normal['print_settings_id']='0.20mm Base wide keys brim @BBL P1P'
(profiles/'process_base.json').write_text(json.dumps(normal,indent=2))

source=root/'final files'/'01_BASE_WIDE_KEYS_BRIM_P1P_PLA.gcode.3mf'
target=root/'print_parts'/'base_and_legs_key_settings.3mf'
with zipfile.ZipFile(source) as zin:
    config=ET.fromstring(zin.read('Metadata/model_settings.config'))
    count=0
    for obj in config.findall('object'):
        if not any(m.get('key')=='name' and m.get('value')=='locking_key' for m in obj.findall('metadata')):
            continue
        count+=1
        for key in ('outer_wall_speed','inner_wall_speed','internal_solid_infill_speed',
                    'sparse_infill_speed','top_surface_speed','gap_infill_speed',
                    'default_acceleration','outer_wall_acceleration','inner_wall_acceleration',
                    'top_surface_acceleration'):
            value=slow[key]
            existing=obj.find(f"metadata[@key='{key}']")
            if existing is not None: obj.remove(existing)
            ET.SubElement(obj,'metadata',key=key,value=';'.join(value) if isinstance(value,list) else value)
    assert count==6
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as zout:
        for name in zin.namelist():
            if name.startswith('Metadata/plate_') or name=='Metadata/slice_info.config': continue
            data=ET.tostring(config,encoding='utf-8',xml_declaration=True) if name=='Metadata/model_settings.config' else zin.read(name)
            zout.writestr(name,data)
print(target)
