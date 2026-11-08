"""Create three self-contained SCAD views and copy their print geometry."""
from pathlib import Path
import re, shutil

root=Path(__file__).resolve().parent
out=root/'final files'
out.mkdir(exist_ok=True)
source=(root/'three_tube_gear_scanner.scad').read_text()
extra='''
module final_base_layout() {
    color("SlateGray") translate([128,70,0]) base();
    for(x=[50,90,130,170]) color("SlateGray") translate([x,135,0]) foot();
    for(x=[50,90]) color("Coral") translate([x,165,0]) motor_clip();
    for(x=[40,75,110,145,180,215]) color("MediumSeaGreen") translate([x,200,0]) locking_key();
}
module final_gears_layout() {
    for(x=[78,128,178]) color("SteelBlue") translate([x,100,0]) socket_gear();
    for(x=[98,128]) color("Orange") translate([x,150,0]) idler();
    color("Goldenrod") translate([158,150,0]) pinion();
    for(x=[78,103,128,153,178]) color("Silver") translate([x,180,0]) washer();
}
'''
source=source.replace('if(part=="assembly") assembly();',extra+'\nif(part=="final_base") final_base_layout();\nelse if(part=="final_gears") final_gears_layout();\nelse if(part=="assembly") assembly();')
views=[('01_base_plate_and_legs','final_base',False,'BOLTLESS REVISION: base, four keyed legs, two motor brackets, six locking keys. No bolts or adhesive.'),
       ('02_gears_and_washers','final_gears',False,'PRINT NOW: six gears plus five separate washers.'),
       ('03_assembled_with_tubes','assembly',True,'VISUALIZATION ONLY: sample tubes and motor are placeholders. Do not print this assembly.')]
for name,part,tubes,note in views:
    text=re.sub(r'^part = .*$',f'part = "{part}";',source,count=1,flags=re.M)
    text=re.sub(r'^show_tubes = .*$',f'show_tubes = {str(tubes).lower()};',text,count=1,flags=re.M)
    (out/(name+'.scad')).write_text('// '+note+'\n// Self-contained snapshot; units are millimeters.\n'+text)
for src,dest in [('boltless_fit_test.3mf','00_boltless_fit_test_unsliced.3mf'),
                 ('base_and_legs.3mf','01_base_plate_and_legs_unsliced.3mf'),
                 ('gears_and_spacers_P1P.3mf','02_gears_and_washers_unsliced.3mf')]:
    shutil.copy2(root/'print_parts'/src,out/dest)
(out/'STL').mkdir(exist_ok=True)
for src in (root/'print_parts').glob('*.stl'): shutil.copy2(src,out/'STL'/src.name)
print(out)
