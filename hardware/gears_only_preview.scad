// Six separate print objects: 3 cap gears, 2 idlers, 1 motor pinion.
// Preview uses the same positions as print_parts/gears_only_P1P.3mf.
use <three_tube_gear_scanner.scad>
for(x=[78,128,178]) color("SteelBlue") translate([x,100,0]) socket_gear();
for(x=[98,128]) color("Orange") translate([x,150,0]) idler();
color("Goldenrod") translate([158,150,0]) pinion();
