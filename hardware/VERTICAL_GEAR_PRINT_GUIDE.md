# Three separate vertical tube holders

**Superseded:** The current design rotates all three tubes together with one motor.
Use [the current print package guide](print_parts/README.md) and the separate STLs
and 3MF plates in `print_parts`. The instructions below describe the earlier layout.

This is a **first print prototype**, not a verified final machine. Each holder
supports **one cap-down tube**. Print one motorized gear station and two separate
plain waiting holders. Move a tube from a waiting holder to the gear station to
scan it. Each tube has its own resting place; the scan station is shared in turn.

## Parts for three tubes

Use `vertical_gear_module.scad` to export these separate STL files:

| OpenSCAD `part` | Quantity | Purpose |
|---|---:|---|
| `base` | 1 | Stationary scan plate, motor holes and socket post |
| `socket_gear` | 1 | Holds the scanned tube cap and rotates around the post |
| `motor_pinion` | 1 | Small gear that fits the motor shaft |
| `foot` | 4 | Holds the scan motor clear of the table |
| `waiting_holder` | 2 | Separate unpowered stands for the other two tubes |

Only **one motor and driver** are needed because one tube is scanned at a time.
The other two motors you own can remain unused for this first build.

## Measure before printing

1. Measure the outside diameter of the **cap** in millimeters. Set
   `cap_diameter` to that number. The default 16 mm is only a placeholder.
   The MRG challenge repository shows two tube sizes but provides no cap
   dimensions, so a physical ruler or caliper measurement is required.
2. Check the motor's two mounting holes, shaft diameter and flat-to-flat
   width. Change the four motor dimensions at the top of the SCAD file if
   yours differs. The values are starting points for a 28BYJ-48, not a
   verified fit for your motor.
3. Check that the shaft extends far enough past the 3 mm base to engage the
   5 mm pinion. Check that the 30 mm feet clear the motor and its connector.
4. Make sure the tube cap is sealed before standing a filled tube cap down.

## Export in OpenSCAD

1. Open `vertical_gear_module.scad`.
2. Change `part` to `"motor_pinion"`. Press **F6** (Render), then **File >
   Export > Export as STL**. Print this small piece first and check the fit on
   the **unpowered** motor shaft. Do not force it.
3. Repeat for `"socket_gear"`; check that the cap enters and lifts out.
4. Repeat for `"base"`, `"foot"`, and `"waiting_holder"`. Print four feet
   and two waiting holders.

## Bambu Studio starting settings

- Use a **0.4 mm nozzle**, **0.20 mm layer height**, **3 walls**, and **15-20%**
  gyroid infill.
- PLA is fine for a dry demonstration. PETG may be preferable if the holder
  will be cleaned often.
- Place the base flat, socket gear with its gear face on the plate, pinion
  flat, and feet upright. Inspect the sliced preview before printing.
- Supports should usually be unnecessary for these shapes. Add a brim if a
  narrow foot or pinion loses adhesion.
- Use Bambu Studio's **Slice plate** time as the real print estimate. As a
  planning range, allow roughly **1-2 hours for the gear station** and **1-2
  more hours for two waiting holders**, depending on printer, material and
  final dimensions.

## Assemble and test

1. Attach four feet under the base. Bolt the motor underneath with its shaft
   pointing up through the clearance hole.
2. Press the small pinion onto the unpowered motor shaft. Slip the socket gear
   over the stationary post. Turn both gears gently by hand; they should mesh
   without binding. A tiny amount of play is expected in this prototype.
3. Put one sealed tube cap in the socket. Confirm that it stays upright, its
   label clears the socket, and the base cannot tip. Fix the base to a larger
   board if needed.
4. Run the motor **without a tube first**, at low speed, then with one tube.
   Stop it fully for each photo. Put the finished tube back in its separate
   holder and transfer the next tube to the gear station. Do not leave it
   running unattended.

The gear teeth are simple prototype teeth. If they bind or skip, adjust the
gear geometry before relying on the scanner. The driver board and power supply
must be identified before providing electrical connections.
