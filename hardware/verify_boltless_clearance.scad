// Expected result: empty. Conservative full-circle rotating gear envelopes
// must not touch new legs, motor brackets, or locking keys at any tooth angle.
use <three_tube_gear_scanner.scad>
module mounts() {
    for(x=[-85,85],y=[-40,30]) {
        translate([x,y,0]) foot();
        translate([x,y-8,45]) locking_key();
    }
    for(s=[-1,1]) {
        translate([s*17.5,-22,37.2]) scale([s,1,1]) motor_clip();
        translate([s*28,-22,45]) rotate([0,0,-90*s]) translate([0,-8,0]) locking_key();
    }
}
module rotating_envelopes() {
    for(x=[-60,0,60]) translate([x,0,45.6]) {
        cylinder(h=5,d=42,$fn=120);
        translate([0,0,5]) cylinder(h=22,d=23,$fn=96);
    }
    for(x=[-30,30]) translate([x,0,45.6]) cylinder(h=5,d=22,$fn=96);
    translate([0,-30,46.2]) cylinder(h=5,d=22,$fn=96);
}
intersection() { mounts(); rotating_envelopes(); }
