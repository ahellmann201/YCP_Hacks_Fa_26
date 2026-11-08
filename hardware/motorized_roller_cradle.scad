// Parametric motorized cradle for one horizontal test tube.
// Export part="base" and part="drive_wheel" as separate STLs.
// Measure the tube before changing the two zero values below.
part = "base"; // "base" or "drive_wheel"
tube_diameter = 0; // outside diameter, millimeters
tube_length = 0;   // overall length, millimeters

// Verify these against your own 28BYJ-48 before printing the full base.
motor_hole_pitch = 35;    // mounting hole center distance
motor_hole_diameter = 4.3;
shaft_round_diameter = 5.1;
shaft_flat_width = 3.2;

// Three 623ZZ bearings: 3 mm bore, 10 mm outside diameter, 4 mm wide.
bearing_diameter = 10;
bearing_width = 4;
bearing_clearance = 0.4;
axle_hole_diameter = 3.3; // M3 bolt clearance

base_thickness = 4;
motor_plate_thickness = 3;
axis_height = 20;
post_thickness = 3;
post_width = 11;
motor_slot_travel = 5;
drive_wheel_width = 5;

assert(tube_diameter > 0 && tube_length > 0,
       "Set measured tube_diameter and tube_length before rendering.");
assert(tube_diameter >= 6 && tube_diameter <= 40,
       "This prototype is intended for tubes 6-40 mm in diameter.");
assert(tube_length >= 45,
       "Tube must be at least 45 mm long for two roller stations.");

// Keep 10 mm bearings from touching on narrow tubes.
roller_spacing = max(tube_diameter * 0.75, bearing_diameter + 2);
base_width = max(65, roller_spacing + 50);
base_length = tube_length + 6;
near_x = 8;
far_x = base_length - 15;
motor_y = -roller_spacing / 2;
idler_y = roller_spacing / 2;
plate_height = axis_height + 22;

module idler_posts(x, y) {
    for (side = [-1, 1])
        translate([x + side * (bearing_width / 2 + bearing_clearance / 2 +
                              post_thickness / 2),
                   y, (base_thickness + axis_height + 4) / 2])
            cube([post_thickness, post_width,
                  axis_height + 4 - base_thickness], center = true);
}

module motor_slot(y) {
    hole_z = axis_height - 8;
    hull()
        for (dz = [-motor_slot_travel, motor_slot_travel])
            translate([motor_plate_thickness / 2, y, hole_z + dz])
                rotate([0, 90, 0])
                    cylinder(h = motor_plate_thickness + 2,
                             d = motor_hole_diameter, center = true, $fn = 32);
}

module cradle_base() {
    difference() {
        union() {
            // Base and upright motor plate. Motor body mounts behind x=0.
            cube([base_length, base_width, base_thickness]);
            cube([motor_plate_thickness, base_width, plate_height]);

            // One idler opposite the drive wheel; two at the far end.
            idler_posts(near_x, base_width / 2 + idler_y);
            idler_posts(far_x, base_width / 2 + motor_y);
            idler_posts(far_x, base_width / 2 + idler_y);
        }

        // Motor shaft opening and adjustable motor mounting slots.
        translate([motor_plate_thickness / 2,
                   base_width / 2 + motor_y, axis_height])
            rotate([0, 90, 0])
                cylinder(h = motor_plate_thickness + 2,
                         d = 12, center = true, $fn = 48);
        for (dy = [-motor_hole_pitch / 2, motor_hole_pitch / 2])
            motor_slot(base_width / 2 + motor_y + dy);

        // Axle bores through each pair of idler posts.
        for (p = [[near_x, idler_y],
                  [far_x, motor_y], [far_x, idler_y]])
            translate([p[0], base_width / 2 + p[1], axis_height])
                rotate([0, 90, 0])
                    cylinder(h = bearing_width + bearing_clearance +
                                 2 * post_thickness + 2,
                             d = axle_hole_diameter, center = true, $fn = 32);
    }
}

module drive_wheel() {
    difference() {
        // 10 mm OD matches the three 623ZZ idler bearing outer diameters.
        cylinder(h = drive_wheel_width, d = bearing_diameter, $fn = 64);

        // Double-flat bore for the common 28BYJ-48 output shaft. Print a
        // single wheel first and tune the two shaft parameters for your motor.
        translate([0, 0, -1])
            linear_extrude(height = drive_wheel_width + 2)
                intersection() {
                    circle(d = shaft_round_diameter, $fn = 64);
                    square([shaft_flat_width,
                            shaft_round_diameter + 1], center = true);
                }
    }
}

if (part == "base") cradle_base();
else if (part == "drive_wheel") drive_wheel();
else assert(false, "Choose part=base or part=drive_wheel.");
