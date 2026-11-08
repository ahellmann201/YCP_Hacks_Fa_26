"""Resolve the official portable Bambu Studio presets into full CLI settings."""
import json, os, zipfile
from pathlib import Path

archive=Path(os.environ['TEMP'])/'codex-bambu-2.9.1'/'bambu.zip'
out=Path(__file__).resolve().parent/'print_parts'/'p1p_profiles'
out.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(archive) as z:
    presets={}
    for filename in z.namelist():
        if filename.startswith('resources/profiles/BBL/') and filename.endswith('.json'):
            item=json.loads(z.read(filename))
            if 'name' in item: presets[item['name']]=item
            presets.setdefault(Path(filename).stem,item)

def resolve(name,chain=()):
    assert name not in chain, 'Preset inheritance cycle'
    item=presets[name]; result={}
    if item.get('inherits'): result.update(resolve(item['inherits'],chain+(name,)))
    for inc in item.get('include',[]): result.update(resolve(inc,chain+(name,)))
    result.update({k:v for k,v in item.items() if k not in ['inherits','include']})
    return result

machine=resolve('Bambu Lab P1P 0.4 nozzle')
process=resolve('0.20mm Standard @BBL P1P')
filament=resolve('Generic PLA @BBL P1P')
process.update({'wall_loops':'4','sparse_infill_density':'25%',
                'sparse_infill_pattern':'gyroid','enable_support':'0',
                'brim_type':'no_brim','outer_wall_speed':['80','80'],
                'inner_wall_speed':['150','150']})
for name,data in [('machine',machine),('process',process),('filament',filament)]:
    (out/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
    print(name,len(data),'settings')
fit_process=dict(process)
fit_process.update({'name':'0.20mm Fit test 6mm brim @BBL P1P',
                    'print_settings_id':'0.20mm Fit test 6mm brim @BBL P1P',
                    'brim_type':'outer_only','brim_width':'6','brim_object_gap':'0.1',
                    'initial_layer_speed':['20','20'],
                    'initial_layer_infill_speed':['30','30']})
fit_filament=dict(filament)
fit_filament.update({'name':'Generic PLA fit test first 3 layers fan off @BBL P1P',
                     'filament_settings_id':['Generic PLA fit test first 3 layers fan off @BBL P1P'],
                     'close_fan_the_first_x_layers':['3']})
for name,data in [('process_fit',fit_process),('filament_fit',fit_filament)]:
    (out/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
key_process=dict(fit_process)
key_process.update({'name':'0.20mm Key retry ZERO GAP @BBL P1P',
                    'print_settings_id':'0.20mm Key retry ZERO GAP @BBL P1P',
                    'brim_width':'8','brim_object_gap':'0',
                    'elefant_foot_compensation':'0'})
for key,value in {'initial_layer_speed':15,'initial_layer_infill_speed':20,
                  'outer_wall_speed':25,'inner_wall_speed':30,
                  'internal_solid_infill_speed':30,'sparse_infill_speed':30,
                  'top_surface_speed':25,'gap_infill_speed':25,
                  'default_acceleration':500,'outer_wall_acceleration':300,
                  'inner_wall_acceleration':500,'top_surface_acceleration':300,
                  'initial_layer_acceleration':300,'initial_layer_travel_acceleration':1500,
                  'travel_acceleration':1500,'travel_speed':150}.items():
    key_process[key]=[str(value),str(value)]
key_filament=dict(fit_filament)
key_filament.update({'name':'Generic PLA key retry @BBL P1P',
                     'filament_settings_id':['Generic PLA key retry @BBL P1P'],
                     'slow_down_layer_time':['15'],'slow_down_min_speed':['10','10']})
for name,data in [('process_key',key_process),('filament_key',key_filament)]:
    (out/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
print({k:v for k,v in machine.items() if k in ['nozzle_type','printer_model','printer_variant','nozzle_diameter','printable_area']})
print({k:v for k,v in filament.items() if k in ['filament_type','filament_diameter','nozzle_temperature','textured_plate_temp']})
