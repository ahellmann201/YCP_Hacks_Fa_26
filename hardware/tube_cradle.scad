// First mechanical prototype: two identical V rests for a horizontal tube.
// Measure the outside diameter of the tube and replace 0 before exporting STL.
tube_diameter = 0; // millimeters; intentionally unset

rest_depth = 14;    // width along the tube axis
base_thickness = 12;
side_wall = 10;
mount_hole_diameter = 3.4; // clearance for an M3 screw
print_gap = 8;

assert(tube_diameter > 0, "Set tube_diameter to the measured outside diameter in millimeters.");

groove_depth = tube_diameter * 0.75;
rest_width = 2 * (groove_depth + side_wall);
rest_height = groove_depth + base_thickness;

module tube_rest() {
    difference() {
        translate([-rest_width / 2, -rest_depth / 2, 0])
            cube([rest_width, rest_depth, rest_height]);

        // Open 90-degree V; the tube touches both sloping walls.
        rotate([90, 0, 0])
            linear_extrude(height = rest_depth + 2, center = true)
                polygon([
                    [-groove_depth - 1, rest_height + 1],
                    [0, base_thickness],
                    [groove_depth + 1, rest_height + 1]
                ]);

        // Optional mounting holes, one on either side of the groove.
        for (x = [-1, 1])
            translate([x * (groove_depth + side_wall / 2), 0, -1])
                cylinder(h = rest_height + 2,
                         d = mount_hole_diameter, $fn = 32);
    }
}

// Print both rests flat on their bases, then position them under the tube.
translate([-(rest_width + print_gap) / 2, 0, 0]) tube_rest();
translate([ (rest_width + print_gap) / 2, 0, 0]) tube_rest();
