// Explanation view only: the real cap gear and washer are lifted off their post.
// Do not print this assembled/exploded visualization.
use <three_tube_gear_scanner.scad>
$fn=96;
color("SlateGray") {
    translate([-25,-25,0]) cube([50,50,3]);
    translate([0,0,3]) cylinder(h=15,d=10);
}
color("Orange") translate([0,0,25]) washer();
color("SteelBlue") translate([0,0,42]) socket_gear();
