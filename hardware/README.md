# Tube rotation prototype

The first print is a pair of V rests in `tube_cradle.scad`. They hold a tube
horizontal and in the camera's view while you check its position and focus.
They are a positioning prototype, not a finished motorized roller mechanism.

1. Measure the tube's **outside diameter** in millimeters. Set
   `tube_diameter` at the top of `tube_cradle.scad` to that number.
2. Open the file in OpenSCAD, render it, and export the two rests as an STL.
   The model deliberately refuses to render until the diameter is set.
3. Print both rests flat on their broad bases. Put them near the ends of the
   tube, clear of the label and cap. Check that the tube sits level and the
   camera can focus on the complete label as you turn it by hand.
4. If the fit is good, fasten the rests to a temporary base through their M3
   clearance holes. Keep the tube removable. Do not tighten anything against
   the tube.

This V-rest design has sliding friction. A motorized version will need a
driven roller and a free-spinning support so the 28BYJ-48 does not have to
drag the tube across the printed V. The roller spacing and motor mount need
the measured tube diameter, tube length, available fasteners, and a check of
the motor's actual mounting dimensions.

## Motorized roller cradle

`motorized_roller_cradle.scad` is the next mechanical design. It uses one
small printed drive wheel on the 28BYJ-48 shaft and three 623ZZ bearings as
free-spinning rollers. The rollers support the tube at two points along its
length while the motor turns it by friction. It does not clamp the tube or
turn its cap.

Parts to gather for this design:

- Three **623ZZ bearings**, nominally 3 mm bore, 10 mm outside diameter,
  4 mm wide. Confirm their dimensions before purchase or printing.
- Three M3 bolts long enough to pass through the two posts and bearing at
  each station, plus nuts and washers. M3 × 20 mm is a starting length.
- Two M3 bolts, nuts, and washers for the motor mounting ears. Check the
  actual ear holes and bolt length on your motor.
- A grippy surface for the drive wheel, such as a thin TPU sleeve. Keep its
  finished outside diameter close to the bearings' 10 mm diameter.

Measure the tube outside diameter and overall length in millimeters. Enter
both at the top of `motorized_roller_cradle.scad`. Check the motor mounting
hole pitch and shaft size against the motor you own. The model uses a 35 mm
mounting pitch and a 5 mm double-flat shaft as **starting values from a
28BYJ-48 drawing**, not as a verified measurement of your individual motor.

In OpenSCAD, choose `part = "drive_wheel"`, render, and export that STL first.
Print and test its fit on the **unpowered** motor shaft. Adjust
`shaft_round_diameter` or `shaft_flat_width` if needed. Then choose
`part = "base"`, render, and export the base STL. Print the base flat on its
bottom. Test-fit the unpowered motor and bearings before fastening the base
to the camera fixture. If the motor shaft does not reach the wheel, do not
force it; measure the projection and revise the motor plate or wheel hub.

Place the motor behind the upright plate with its shaft through the large
opening. Its small drive wheel sits opposite the near idler bearing. Put the
other two bearings at the far end. The tube rests on the wheel and bearings.
Turn the tube by hand first: it should remain level, stay in focus, and turn
without binding or slipping. Stop rotation completely before taking a photo.

The base and wheel are parameterized models, not verified STLs. OpenSCAD is
not installed in this workspace, and the tube measurements have not been
provided yet. Check the rendered model and first printed fit before making
the electrical connection.

Mechanical reference: [28BYJ-48 5 V drawing](https://www.mouser.com/datasheet/2/272/step-motor-5v-28byj48-datasheet-1864397.pdf).
Electrical reference: [Arduino UNO Q full pinout](https://docs.arduino.cc/resources/pinouts/ABX00162-full-pinout.pdf).

## Electrical checkpoint

The motor photo shows **28BYJ-48, 5 VDC**. The driver board is visible only
from the solder side, and the power supply is not identified yet. Do not
connect the motor to UNO Q GPIO pins or energize the driver until the front
of the driver board, its connector labels, and the power supply output label
are confirmed. The first electrical test will be a separate slow turn and
pause sequence, with manual photos and no OCR integration.
