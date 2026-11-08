// Sample the new gear pair through one tooth period; result should be empty.
use <three_tube_gear_scanner.scad>
for(i=[0:20]) translate([0,50*i,0])
    linear_extrude(1) intersection() {
        rotate(i*9/20) gear2d(40);
        translate([30,0]) rotate(9-2*i*9/20) gear2d(20);
    }
