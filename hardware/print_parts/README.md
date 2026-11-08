# Three-tube scanner: print separately, then assemble

One motor turns three cap-down tubes together. Each blue socket gear is a separate
part; none of the moving gears is fused to the stationary base. The fixed posts
are part of the base. Slide the gears onto those posts after printing.

## Open these files in Bambu Studio

- `gears_and_legs.3mf`: 15 separate objects, already placed apart at z=0.
- `base_plate.3mf`: the stationary base alone, 190 x 90 mm.

These are **geometry-only, unsliced 3MF files**. They contain no printer profile,
filament profile, support settings or G-code. Choose the actual printer, nozzle
and filament before slicing. Do not send an assembled preview to the printer.

If importing the individual STLs, import them as separate objects, not as one
multipart assembly. Keep 100% scale. The large base needs a usable build area
of at least 190 x 90 mm; if it does not fit, revise/split the base rather than
shrinking it, because shrinking changes the cap and motor fits.

## Part quantities

| STL | Quantity | Function |
|---|---:|---|
| base.stl | 1 | Stationary plate and fixed gear posts |
| socket_gear.stl | 3 | 40-tooth gear and 17.6 mm cap socket |
| idler.stl | 2 | 20-tooth intermediate gear |
| pinion.stl | 1 | 20-tooth gear on the motor shaft |
| foot.stl | 4 | Separate 42 mm legs with through-bolt holes |
| washer.stl | 5 | 0.6 mm spacer beneath each free-spinning gear |

The cap socket is 9 mm deep. Its 17.6 mm opening gives a nominal 0.3 mm clearance
around your 17 mm cap. Add a thin paper shim if needed so the cap turns with the
socket without slipping. Do not force the tube into a tight socket.

## First print and slicing

1. Print one socket gear and one pinion first. Test cap grip and motor-shaft fit
   before committing to the complete set. The motor bore is a starting size,
   not a verified fit to your individual motor.
2. With a 0.4 mm nozzle, start with PLA, 0.20 mm layers, 4 walls and 25% infill.
   Inspect the fine teeth in Preview. Keep all gears flat on their bottom faces;
   the cup openings face upward. Feet stand upright. Washers lie flat.
3. Supports should normally be off for these upright parts. The small blind
   post bore in each socket has a bridged ceiling; check and clean it after
   printing. Keep support material out of the gear teeth and shaft holes.
4. Slice the two plates separately. Check that every moving gear starts on the
   build plate as its own object. Nothing should print in place around a post.
5. Read the time and filament estimates from the actual slice. No reliable
   printer-specific estimate has been generated yet.

## Assembly and motor clearance

1. Attach the four legs to the base. M3 x 45 mm bolts and M3 nuts are starting
   choices for the 42 mm legs and 3 mm plate. Nuts seat in the hex pockets at
   the floor end. Check bolt tips do not protrude below the feet.
2. Mount the motor under the plate, shaft pointing through the 12 mm opening.
   The revised plate has slots for mounting-ear position adjustment. The ear
   line is nominally 8 mm behind the shaft, adjustable by 4 mm either way.
   Verify this against your motor. Use suitable screws/nuts through its ears.
3. The plate has 42 mm of clear height underneath. The motor body shown in the
   preview is only a 20 mm illustrative envelope. Check the real motor body,
   connector and cable fit before tightening the mount.
4. Slip one 0.6 mm washer over each of the five fixed posts, then slide on the
   three socket gears and two idlers. They must turn freely. Remove print burrs
   if needed; do not glue a moving gear or its washer to the post.
5. Fit the pinion on the motor shaft, level with the other gears. The shaft must
   project beyond the 3 mm plate and 0.6 mm running gap far enough to engage
   the 5 mm-thick pinion. Measure this; do not assume the drawing proves the fit.
6. With the motor unpowered, turn the gears by hand. Then test at low speed
   without tubes, followed by one tube and finally three. Stop for each photo.

## What was checked

All six exported STL types are closed, connected meshes and start at z=0. The
3MF plate objects have non-overlapping bounding boxes. The ideal gear outlines
showed no overlap at 21 sampled positions through a tooth cycle. Physical fit,
friction, motor torque and printer tolerances still require the test prints.

This package supersedes the earlier single-station / two-waiting-holder guide.
Do not print the old layout for this three-tube drive.
