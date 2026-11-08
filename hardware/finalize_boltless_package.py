"""Validate Bambu slices, extract raw G-code, and package current boltless files."""
from pathlib import Path
from collections import Counter
import hashlib, itertools, json, re, zipfile, shutil
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parent
out=root/'final files'
jobs={
    '00_boltless_fit_test_P1P_PLA':dict(fit_coupon=1,test_peg=1,motor_clip=1,locking_key=1),
    '01_BASE_WIDE_KEYS_BRIM_P1P_PLA':dict(base=1,foot=4,motor_clip=2,locking_key=6),
    '02_gears_and_washers_P1P_PLA':dict(socket_gear=3,idler=2,pinion=1,washer=5),
}
report={}
for name,expected in jobs.items():
    with zipfile.ZipFile(out/(name+'.gcode.3mf')) as z:
        settings=json.loads(z.read('Metadata/project_settings.config'))
        assert settings['printer_model']=='Bambu Lab P1P'
        assert settings['nozzle_diameter']==['0.4']
        assert settings['filament_type']==['PLA']
        assert settings['filament_diameter']==['1.75']
        assert settings['curr_bed_type']=='Textured PEI Plate'
        assert settings['enable_support']=='0'
        if name.startswith('01_'):
            assert settings['brim_type']=='outer_only' and settings['brim_width']=='8'
            assert settings['brim_object_gap']=='0' and settings['elefant_foot_compensation']=='0'
            assert settings['initial_layer_speed']==['15','15']
            assert settings['close_fan_the_first_x_layers']==['3']
        if name.startswith('00_'):
            assert settings['brim_type']=='outer_only' and settings['brim_width']=='6'
            assert settings['brim_object_gap']=='0.1'
            assert settings['initial_layer_speed']==['20','20']
            assert settings['close_fan_the_first_x_layers']==['3']
        plate=json.loads(z.read('Metadata/plate_1.json'))
        objs=plate['bbox_objects']
        assert Counter(o['name'] for o in objs)==expected
        if name.startswith('01_'):
            with zipfile.ZipFile(out/'04_WIDE_T_KEY_ZERO_GAP_P1P_PLA.gcode.3mf') as reference:
                key_box=json.loads(reference.read('Metadata/plate_1.json'))['bbox_objects'][0]['bbox']
            for o in objs:
                if o['name']=='locking_key':
                    # Bambu's plate bounding boxes include the brim, so compare
                    # against the verified wide-key retry with the same brim.
                    assert abs((o['bbox'][2]-o['bbox'][0])-(key_box[2]-key_box[0]))<0.1
            model_config=ET.fromstring(z.read('Metadata/model_settings.config'))
            keys=0
            for obj in model_config.findall('object'):
                values={m.get('key'):m.get('value') for m in obj.findall('metadata')}
                if values.get('name')=='locking_key':
                    keys+=1
                    assert values['outer_wall_speed'] in ('25','25;25')
                    assert values['inner_wall_speed'] in ('30','30;30')
                    assert values['default_acceleration'] in ('500','500;500')
            assert keys==6
        for o in objs:
            x0,y0,x1,y1=o['bbox']
            assert 0<=x0<x1<=256 and 0<=y0<y1<=256
            assert x0>=18 or y0>=28, 'P1P exclusion area overlap'
        for a,b in itertools.combinations(objs,2):
            a,b=a['bbox'],b['bbox']
            assert a[2]<b[0] or b[2]<a[0] or a[3]<b[1] or b[3]<a[1]
        info=ET.fromstring(z.read('Metadata/slice_info.config'))
        meta={x.attrib['key']:x.attrib['value'] for x in info.findall('./plate/metadata')}
        assert meta['outside']=='false' and meta['support_used']=='false'
        raw=z.read('Metadata/plate_1.gcode')
        if name.startswith('00_'):
            assert len(re.findall(rb'^; FEATURE: Brim\r?$',raw,re.M))==4
        digest=hashlib.md5(raw).hexdigest()
        assert digest.upper()==z.read('Metadata/plate_1.gcode.md5').decode().strip().upper()
        (out/(name+'.gcode')).write_bytes(raw)
        (out/(name+'_preview.png')).write_bytes(z.read('Metadata/plate_1.png'))
        report[name]={
            'objects':expected,'estimated_seconds':int(meta['prediction']),
            'filament_g':float(meta['weight']),'gcode_md5':digest,
            'validated':'P1P/0.4/PLA, separate objects, bed bounds, exclusion area, no supports, G-code checksum',
        }
(out/'validation_summary.json').write_text(json.dumps(report,indent=2))
for ext in ('.gcode.3mf','.gcode','_preview.png'):
    shutil.copy2(out/('01_BASE_WIDE_KEYS_BRIM_P1P_PLA'+ext),
                 out/('01_boltless_base_P1P_PLA'+ext))
shutil.copy2(out/'00_boltless_fit_test_P1P_PLA.gcode.3mf',
             out/'00_boltless_fit_test_BRIM_P1P_PLA.gcode.3mf')

guide='''BOLTLESS THREE-TUBE SCANNER - CURRENT REVISION

No bolts, nuts, glue, tape or cable ties are required by this design.
Printed tapered keys retain four legs and two motor brackets. Fit and load
capacity remain physically untested. Print the small fit test first.

FILES AND PRINT ORDER
00_boltless_fit_test_BRIM_P1P_PLA.gcode.3mf
  A square test plate, a short test leg, one motor bracket and one key.
  Estimated 25 min 13 sec, 4.93 g PLA. Updated with 6 mm outer brims.
  The file without BRIM in its name is also updated to the same contents.
  Reopen the new BRIM file; an old project already open in Studio is not updated.
01_BASE_WIDE_KEYS_BRIM_P1P_PLA.gcode.3mf
  Base, four full-height legs, two identical motor brackets, six keys.
  BASE_ESTIMATE_PLACEHOLDER
  Includes six wide keys; your two successful retry keys can be spares.
  The older 01_boltless_base filename now contains the same updated slice.
02_gears_and_washers_P1P_PLA.gcode.3mf
  Three cap-holder gears, two idlers, one motor pinion, five washers.
  Estimated 1 hr 35 min 5 sec, 34.93 g PLA. This gear slice is unchanged.

Each sliced 3MF contains its print G-code. Matching raw .gcode files are
extracted without edits. Estimates include slicer startup allowance; actual
time can vary. These files prepare a print; no printer has been started.

All slices: Bambu Lab P1P, standard 0.4 mm nozzle, Generic PLA 1.75 mm,
Textured PEI Plate, 0.20 mm layers, 4 walls, 25% gyroid infill, supports off,
220 C nozzle and 65 C bed. Check the installed build plate matches.
FIT TEST ONLY: 6 mm outer brim, 0.1 mm brim-object gap, first-layer wall speed
20 mm/s and infill 30 mm/s, part-cooling fan off for first 3 layers. Parts
are spread farther apart and away from the plate edges for brim clearance.
BASE: 8 mm outer brim, zero gap, elephant-foot compensation off; first layer
15/20 mm/s and first 3 layers fan off. Keys retain later walls 25/30 mm/s and
reduced acceleration from the successful retry; larger parts use normal speeds.
Gears retain their previous slice, with brims off.
After cooling, peel/trim the thin outer brim off each fit-test part before
checking the joint. Remove edge remnants carefully without trimming the
actual peg or changing the square test opening.
For a different printer/material/nozzle/plate, change the profile and reslice.
Keep 100% scale; scaling changes the cap, shaft and locking-joint fits.

Open the chosen .gcode.3mf in Bambu Studio and review Preview before sending
it through your usual printer connection or transferring it to microSD.
Use only the sliced files for printing. The *_unsliced.3mf files are geometry
for editing/reslicing. Individual STL files are in STL/.

THREE OPENSCAD FILES
01_base_plate_and_legs.scad: current boltless base plate layout, including
  legs, motor brackets and keys, all separate and touching the print bed.
02_gears_and_washers.scad: gears and washers laid out separately.
03_assembled_with_tubes.scad: assembly preview only. DO NOT PRINT IT.
  The motor and sample tubes are illustrative, not printed components.
The sliced *_preview.png files show the print layout. Colors identify parts in
the preview; the actual print uses one filament color.

TEST THE LOCKING JOINT FIRST
1. Let the four fit-test objects cool; remove them and trim loose strings.
2. Insert the short test leg's square peg through the square test plate from
   underneath. Its round shoulder should sit against the underside.
3. With the key flat side against the top of the test plate, push its thin
   end into the horizontal slot in the peg. Slide it until finger-tight.
   The key's wider end remains outside as a handle. It need not go fully in.
4. The plate should not rattle, the key should stay in place, and the peg
   must not crack or bend. Pull the key out to release the joint. Do not hammer.
5. Check the motor bracket's small locating pin fits one mounting-ear hole
   on your actual 28BYJ-48. It should enter without force.
6. If either fit fails, stop before the large print. Minor burrs can be
   removed; loose or consistently tight joints need CAD adjustment/reslicing.
   Do not substitute adhesive for a failed locking joint.

FULL ASSEMBLY
1. Insert the four long legs through the four corner square holes from
   below. The 42 mm round portions stay below the board. Insert one key
   sideways through each exposed peg, flat side down, until finger-tight.
2. Hold the unpowered 28BYJ-48 5V motor below the shaft opening, shaft up.
   Orient its mounting ears toward the two remaining square holes.
3. Place one motor bracket under each ear. Each small round pin enters an
   ear hole; each taller square peg goes through the nearby square board
   hole. Turn the second identical bracket 180 degrees to fit the other side.
4. Insert the last two keys through the motor-bracket peg slots above the
   board. The wide handles point outward, away from the middle gear. Tighten
   gently and evenly until the ears are held against the board. The motor
   must not rock or move. If it does, do not run it; revise the mount fit.
5. Slide one 0.6 mm washer over each of the five fixed axle posts.
6. Place the three large cup gears on the tall posts and the two small
   round-bore idlers on the short posts. Cups face upward. Turn these gears
   gently by hand before engaging the motor pinion; nothing should bind.
7. Fit the remaining small double-flat-hole gear on the motor shaft. The
   assembly preview raises it 0.6 mm relative to the other gear bottoms to
   clear the nominal round shaft shoulder, leaving about 4.4 mm tooth-height
   overlap. Verify on your motor; do not force it down over the round section.
8. Check the pinion grips, stays clear of the board and meshes freely. It
   has no set screw; a loose pinion needs a revised bore/hub and reprint.
9. Connect the appropriate motor driver and rated supply. Run slowly without
   tubes first. Stop for clicking, stalls, movement of the mount or lifted gears.
10. Add one empty securely capped tube, cap-down, then the other two. Check
    wobble, cap grip and closure. A thin paper shim may help a loose cap fit.
    Test actual loads only after the empty-tube check succeeds.

SIZE AND MOTION
Board: 190 x 90 x 3 mm. Four legs give 42 mm clearance under the board.
Legs are 18 mm in diameter and 51 mm total printed height including pegs.
Keys project slightly beyond the board edges; assembled footprint is about
190 x 99 mm, excluding wires. Height depends on the real tube length.
Socket bore: 17.6 mm, depth: 9 mm, for the stated 17 mm cap diameter.
All three tubes rotate together, same speed and direction. The 20-tooth
motor pinion drives 40-tooth output gears: two output-shaft turns of the
motor give one tube revolution. This fixed train cannot select one tube.
For camera sampling, stop, allow vibration to settle, then capture and crop.

WHY PARTS LOOK RAISED
Angled print-layout views make the rear row look higher. All printed objects
start at bed Z=0. In the assembly view, legs lift the board for motor clearance
and washers lift the gears 0.6 mm above it. The cup and its large gear are one
printed part. Gears are never printed fused to the board or the axle posts.

LIMITATIONS TO CHECK
- Printed wedges depend on friction and can loosen; inspect before each run.
  Finger-tight only. Too much force can split the peg along print layers.
- A 3 mm board can flex or warp. Check gear alignment. Making it thicker also
  changes the joint slots and motor-shaft reach, so do not change one alone.
- Gear/post clearance is 0.4 mm on diameter (0.2 mm per side). First-layer
  burrs or hole shrinkage can cause binding. Remove burrs or revise the fit.
- The underside blind bore in each cup has a short bridged roof. Sagging
  plastic can rub the post tip; the gear must rest on its washer and turn freely.
- Thin washers can curl or tear. Replace damaged ones.
- No upper gear retainers are provided. Keep the unit upright; if gears lift
  during operation, stop and revise retention rather than increasing speed.
- Tall/heavy tubes may need an upper guide. Secure cap grip and closure are
  not yet validated. Start with empty tubes; check caps do not loosen.
- Motor shaft grip, ear thickness and mounting fit still require checking
  on the actual motor. Printed locator pins are nominal 3.6 mm for 4.2 mm holes.
- A loose motor, excessive friction or too much acceleration can cause lost
  steps. Motor heating can affect nearby PLA. Test at low speed first.

VALIDATION
All exported STL types checked as closed meshes, one connected solid each,
starting at Z=0. Slices checked for expected part counts, separated objects,
P1P bed bounds and front-left exclusion zone, correct printer/material/nozzle,
no supports, and matching raw G-code checksum. See validation_summary.json.
These digital checks do not replace a physical fit or loaded-operation test.

MOTOR REFERENCE
User confirmed 28BYJ-48 5V. Nominal shaft diameter 5 mm, flats 3 mm, mounting
spacing 35 mm, offset 8 mm. CAD bore is 5.1 mm / 3.2 mm across flats.
https://www.mouser.com/datasheet/2/813/step_motor_5v_28byj48_datasheet-3247591.pdf
'''
retry_note=out/'04_RETRY_INSTRUCTIONS.txt'
base_stats=report['01_BASE_WIDE_KEYS_BRIM_P1P_PLA']
hours,remainder=divmod(base_stats['estimated_seconds'],3600)
minutes,seconds=divmod(remainder,60)
guide=guide.replace('BASE_ESTIMATE_PLACEHOLDER',
    f"Estimated {hours} hr {minutes} min {seconds} sec, {base_stats['filament_g']:.2f} g PLA.")
if retry_note.exists(): guide=retry_note.read_text()+guide
(out/'PRINT_AND_ASSEMBLY.txt').write_text(guide,encoding='utf-8')
with zipfile.ZipFile(root/'final_print_files.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(out.rglob('*')):
        if f.is_file(): z.write(f,f.relative_to(out))
print(json.dumps(report,indent=2))
