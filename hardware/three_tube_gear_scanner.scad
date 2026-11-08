// Three cap-down tubes, one motor: all rotate together on separate axes.
// Cap outside diameter supplied by user: 17 mm. Motor fit remains unverified.
part = "assembly"; // preview only. Export base, socket_gear, idler, pinion, foot, washer separately.
show_tubes = false; // hide illustrative tubes; never export assembly for printing
cap_diameter = 17; // 1.7 cm cap outside diameter
cap_height = 10;
tube_diameter = 13;
tube_height = 95;
cap_clearance = 0.6; // 17.6 mm socket bore: 0.3 mm per side for fit / paper shim
motor_hole_pitch = 35;
motor_ear_offset = 8; // shaft is offset from mounting-ear line; verify on your motor
shaft_diameter = 5.1;
shaft_flat_width = 3.2;
gear_module = 1;
output_teeth = 40;
small_teeth = 20;
gear_height = 5;
pressure_angle = 20;
backlash = 0.18; // total tooth thickness reduction at pitch circle, mm
post_diameter = 10;
post_clearance = 0.4;
base_thickness = 3;
foot_height = 42; // clear space below plate; legs lock with printed tapered keys
peg_width = 8;
peg_clearance = 0.4;
key_width = 3.4;
key_slot_width = 3.8;
motor_ear_gap = 1.8; // nominal 1.5 mm ears; wedge draws bracket toward board
motor_clip_thickness = 3;
motor_peg_offset = 10.5; // outboard of each mounting-ear hole
pinion_lift = 0.6; // nominal clearance over the motor's unflattened shaft shoulder
floor_height = 13;
socket_depth = 9;
running_gap = 0.6; // separate printed thrust washer supports each free-spinning gear
center_distance = gear_module*(output_teeth+small_teeth)/2;
station_pitch = 2*center_distance;
$fn = 96;

assert(cap_diameter > 0 && cap_diameter+6 < gear_module*(output_teeth-2.5),
       "Cap is too wide for this gear; increase output gear size.");
function polar(r,a)=[r*cos(a),r*sin(a)];
function involute(a)=tan(a)-a*PI/180;
function flank_angle(r,rb,rp,n)=90/n-backlash/(2*rp)*180/PI
    +(involute(pressure_angle)-involute(acos(rb/r)))*180/PI;

module gear2d(n) {
    rp=gear_module*n/2;
    rb=rp*cos(pressure_angle);
    rr=rp-1.25*gear_module;
    ra=rp+gear_module;
    start=max(rr,rb);
    steps=12;
    left=[for(i=[0:steps]) let(r=start+(ra-start)*i/steps)
        polar(r,flank_angle(r,rb,rp,n))];
    right=[for(i=[steps:-1:0]) let(r=start+(ra-start)*i/steps)
        polar(r,-flank_angle(r,rb,rp,n))];
    union() {
        circle(r=rr);
        for(i=[0:n-1]) rotate(i*360/n)
            polygon(concat([polar(rr-0.05,flank_angle(start,rb,rp,n))],left,right,
                           [polar(rr-0.05,-flank_angle(start,rb,rp,n))]));
    }
}

module base() {
    difference() {
        union() {
            translate([-station_pitch-35,-50,0])
                cube([2*station_pitch+70,90,base_thickness]);
            for(x=[-station_pitch,0,station_pitch])
                translate([x,0,base_thickness]) cylinder(h=15,d=post_diameter);
            for(x=[-center_distance,center_distance])
                translate([x,0,base_thickness]) cylinder(h=4.8,d=post_diameter);
        }
        translate([0,-center_distance,-1]) cylinder(h=base_thickness+2,d=12);
        // Two removable printed motor brackets pass through square sockets.
        for(x=[-1,1])
            translate([x*(motor_hole_pitch/2+motor_peg_offset),-center_distance+motor_ear_offset,-1])
                linear_extrude(base_thickness+2) square(peg_width+peg_clearance,center=true);
        // Legs register in square sockets; printed keys retain them above the board.
        for(x=[-station_pitch-25,station_pitch+25],y=[-40,30])
            translate([x,y,-1]) linear_extrude(base_thickness+2)
                square(peg_width+peg_clearance,center=true);
    }
}
module socket_gear() {
    difference() {
        union() {
            linear_extrude(height=gear_height,convexity=10) gear2d(output_teeth);
            translate([0,0,gear_height])
                cylinder(h=floor_height+socket_depth,d=cap_diameter+6);
        }
        translate([0,0,-0.1]) cylinder(h=15.3,d=post_diameter+post_clearance);
        translate([0,0,gear_height+floor_height])
            cylinder(h=socket_depth+0.1,d=cap_diameter+cap_clearance);
    }
}
module idler() {
    difference() {
        linear_extrude(height=gear_height,convexity=10) gear2d(small_teeth);
        translate([0,0,-0.1]) cylinder(h=gear_height+0.2,d=post_diameter+post_clearance);
    }
}
module pinion() {
    difference() {
        linear_extrude(height=gear_height,convexity=10) gear2d(small_teeth);
        translate([0,0,-0.1]) linear_extrude(gear_height+0.2)
            intersection() {
                circle(d=shaft_diameter);
                square([shaft_flat_width,shaft_diameter+1],center=true);
            }
    }
}
module foot(height=foot_height) {
    difference() {
        union() {
            cylinder(h=height,d=18);
            translate([-peg_width/2,-peg_width/2,height-0.1])
                cube([peg_width,peg_width,base_thickness+6.1]);
        }
        translate([-key_slot_width/2,-peg_width/2-1,height+base_thickness-0.2])
            cube([key_slot_width,peg_width+2,3.7]);
    }
}
module test_peg() { foot(6); }
module locking_key() {
    // Flat underside on print bed. Slide the thin end through the peg slot.
    // The long taper replaces a bolt; finger-tight only, no snap flexure.
    polyhedron(points=[[-key_width/2,0,0],[key_width/2,0,0],
        [key_width/2,24,0],[-key_width/2,24,0],
        [-key_width/2,0,2.8],[key_width/2,0,2.8],
        [key_width/2,24,4.2],[-key_width/2,24,4.2]],
        faces=[[0,3,2,1],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,6,7]],convexity=4);
    // Wider paddle grip adds bed contact without enlarging the mating stem.
    // Tapered outer corners clear the adjacent gears on both motor brackets.
    linear_extrude(4.2) polygon([
        [-key_width/2,18.5],[-8,20],[-8,21],[-4.5,27],
        [4.5,27],[8,21],[8,20],[key_width/2,18.5]]);
}
module motor_clip() {
    difference() {
        union() {
            // Pad under one motor ear; body remains clear inboard of the pad.
            translate([-3,-5,0]) cube([motor_peg_offset+7,10,motor_clip_thickness]);
            translate([0,0,motor_clip_thickness-0.1]) cylinder(h=1.3,d=3.6);
            translate([motor_peg_offset-peg_width/2,-peg_width/2,motor_clip_thickness-0.1])
                cube([peg_width,peg_width,motor_ear_gap+base_thickness+6.1]);
        }
        translate([motor_peg_offset-peg_width/2-1,-key_slot_width/2,
                   motor_clip_thickness+motor_ear_gap+base_thickness-0.2])
            cube([peg_width+2,key_slot_width,3.7]);
    }
}
module fit_coupon() {
    // Optional quick check for a leg/bracket peg and key; same thickness as base.
    difference() {
        translate([-10,-10,0]) cube([20,20,base_thickness]);
        translate([0,0,-0.1]) linear_extrude(base_thickness+0.2)
            square(peg_width+peg_clearance,center=true);
    }
}
module washer() {
    difference() {
        cylinder(h=running_gap,d=16);
        translate([0,0,-0.1]) cylinder(h=running_gap+0.2,d=post_diameter+0.5);
    }
}
module tube_example() {
    color("MediumPurple") cylinder(h=cap_height,d=cap_diameter);
    color([0.65,0.83,0.92,0.45]) translate([0,0,cap_height])
        cylinder(h=tube_height,d=tube_diameter);
    color("Ivory") translate([0,0,cap_height+20])
        difference() {
            cylinder(h=45,d=tube_diameter+0.4);
            translate([0,0,-0.1]) cylinder(h=45.2,d=tube_diameter);
        }
}
module motor_example() {
    // Nominal datasheet envelope, not a printable motor or verified physical fit.
    color("DimGray") difference() {
        union() {
            cylinder(h=19,d=28);
            for(side=[-1,1]) translate([0,0,17.5]) linear_extrude(1.5)
                hull() { circle(d=7); translate([side*motor_hole_pitch/2,0]) circle(d=7); }
        }
        for(side=[-1,1]) translate([side*motor_hole_pitch/2,0,17.4]) cylinder(h=1.7,d=4.2);
    }
    color("Silver") translate([0,-motor_ear_offset,19]) {
        cylinder(h=4,d=5);
        translate([0,0,4]) linear_extrude(6)
            intersection() { circle(d=5); square([3,6],center=true); }
    }
}
module assembly() {
    z=foot_height+base_thickness+running_gap;
    color("SlateGray") translate([0,0,foot_height]) base();
    for(x=[-station_pitch-25,station_pitch+25],y=[-40,30])
        color("SlateGray") translate([x,y,0]) foot();
    for(x=[-station_pitch-25,station_pitch+25],y=[-40,30])
        color("MediumSeaGreen") translate([x,y-8,foot_height+base_thickness]) locking_key();
    for(side=[-1,1]) {
        color("Coral") translate([side*motor_hole_pitch/2,-center_distance+motor_ear_offset,
                                foot_height-motor_ear_gap-motor_clip_thickness])
            scale([side,1,1]) motor_clip();
        color("MediumSeaGreen") translate([side*(motor_hole_pitch/2+motor_peg_offset),
                                -center_distance+motor_ear_offset,foot_height+base_thickness])
            rotate([0,0,-90*side]) translate([0,-8,0]) locking_key();
    }
    for(x=[-station_pitch,0,station_pitch]) {
        color("Silver") translate([x,0,foot_height+base_thickness]) washer();
        color("SteelBlue") translate([x,0,z]) socket_gear();
        if(show_tubes) translate([x,0,z+gear_height+floor_height]) tube_example();
    }
    for(x=[-center_distance,center_distance])
        color("Orange") translate([x,0,z]) rotate(180/small_teeth) idler();
    for(x=[-center_distance,center_distance])
        color("Silver") translate([x,0,foot_height+base_thickness]) washer();
    color("Goldenrod") translate([0,-center_distance,z+pinion_lift]) rotate(180/small_teeth) pinion();
    translate([0,-center_distance+motor_ear_offset,foot_height-19]) motor_example();
}
module print_layout() {
    // Detached parts for the first plate; base is printed on a separate plate.
    for(x=[25,75,125]) color("SteelBlue") translate([x,25,0]) socket_gear();
    for(x=[25,55]) color("Orange") translate([x,65,0]) idler();
    color("Goldenrod") translate([85,65,0]) pinion();
    for(x=[20,45,70,95]) color("SlateGray") translate([x,100,0]) foot();
    for(x=[20,45,70,95,120]) color("Silver") translate([x,130,0]) washer();
}
if(part=="assembly") assembly();
else if(part=="print_layout") print_layout();
else if(part=="base") base();
else if(part=="socket_gear") socket_gear();
else if(part=="idler") idler();
else if(part=="pinion") pinion();
else if(part=="foot") foot();
else if(part=="motor_clip") motor_clip();
else if(part=="locking_key") locking_key();
else if(part=="fit_coupon") fit_coupon();
else if(part=="test_peg") test_peg();
else if(part=="washer") washer();
else assert(false,"Choose assembly, base, socket_gear, idler, pinion, foot, or washer.");
