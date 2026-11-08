// One powered cap-down scan station plus separate waiting holders.
// CONCEPT PROTOTYPE: measure your cap and motor before making final STLs.
// OpenSCAD: choose each part and export its STL separately.

part = "assembly"; // preview; select an individual part for STL export
cap_diameter = 16;       // REPLACE with measured outside diameter of the cap (mm)
cap_clearance = 0.6;     // adjust after a small socket test print
cap_socket_depth = 9;

// Starting dimensions for a 28BYJ-48 motor; verify against your motor.
motor_hole_pitch = 35;
motor_hole_diameter = 4.2;
shaft_round_diameter = 5.1;
shaft_flat_width = 3.2;

gear_module = 1.25;
pinion_teeth = 16;
socket_teeth = 32;
gear_height = 5;
base_thickness = 3;
base_width = 72;
base_length = 100;
foot_height = 30; // verify motor and connector clearance below the base
post_diameter = 10;
post_clearance = 0.35;
motor_clearance_diameter = 12;
socket_floor = 13; // deep blind bore for a steadier vertical spindle
gear_center_distance = gear_module * (pinion_teeth + socket_teeth) / 2;

assert(cap_diameter >= 10 && cap_diameter <= 30,
       "Check cap_diameter; expected a cap between 10 and 30 mm.");

function pt(r,a) = [r*cos(a),r*sin(a)];

// Simple trapezoid-tooth prototype for low-speed fit testing, not a precision involute gear.
module prototype_gear(teeth) {
    pitch_r = gear_module * teeth / 2;
    root_r = pitch_r - 1.25*gear_module;
    outer_r = pitch_r + gear_module;
    step = 360 / teeth;
    union() {
        circle(r=root_r, $fn=teeth*12);
        for (i=[0:teeth-1]) {
            a = i*step;
            polygon([
                pt(root_r-0.1,a-step*0.29),
                pt(outer_r,a-step*0.19),
                pt(outer_r,a+step*0.19),
                pt(root_r-0.1,a+step*0.29)
            ]);
        }
    }
}

module base() {
    difference() {
        union() {
            translate([-base_length/2,-base_width/2,0])
                cube([base_length,base_width,base_thickness]);
            // The socket gear slips over this stationary post and can be lifted off.
            translate([gear_center_distance/2,0,base_thickness])
                cylinder(h=gear_height+10,d=post_diameter,$fn=64);
        }
        // Motor mounts under the other station; shaft points upward.
        translate([-gear_center_distance/2,0,-1])
            cylinder(h=base_thickness+2,d=motor_clearance_diameter,$fn=64);
        for (y=[-motor_hole_pitch/2,motor_hole_pitch/2])
            translate([-gear_center_distance/2,y,-1])
                cylinder(h=base_thickness+2,d=motor_hole_diameter,$fn=32);
    }
}

module socket_gear() {
    pitch_r = gear_module * socket_teeth / 2;
    outer_r = pitch_r + gear_module;
    cup_outer_d = cap_diameter+6;
    cup_height = cap_socket_depth + socket_floor;
    difference() {
        union() {
            linear_extrude(height=gear_height) prototype_gear(socket_teeth);
            translate([0,0,gear_height])
                cylinder(h=cup_height,d=cup_outer_d,$fn=96);
        }
        // Blind post bore from underneath. Leaves the cap socket floor intact.
        translate([0,0,-0.1])
            cylinder(h=gear_height+10.2,d=post_diameter+post_clearance,$fn=64);
        translate([0,0,gear_height+socket_floor])
            cylinder(h=cap_socket_depth+0.2,
                     d=cap_diameter+cap_clearance,$fn=96);
    }
}

module motor_pinion() {
    difference() {
        linear_extrude(height=gear_height) prototype_gear(pinion_teeth);
        translate([0,0,-0.1])
            linear_extrude(height=gear_height+0.2)
                intersection() {
                    circle(d=shaft_round_diameter,$fn=64);
                    square([shaft_flat_width,shaft_round_diameter+1],center=true);
                }
    }
}

module foot() {
    // Print four and attach below the base near its corners.
    cylinder(h=foot_height,d=12,$fn=64);
}

module waiting_holder() {
    // Print two. Each is a separate, unpowered cap-down tube stand.
    difference() {
        cylinder(h=14,d=56,$fn=96);
        translate([0,0,5])
            cylinder(h=9.2,d=cap_diameter+cap_clearance,$fn=96);
    }
}

module assembly() {
    color("SlateGray") translate([0,0,foot_height]) base();
    for (x=[-40,40], y=[-26,26])
        color("SlateGray") translate([x,y,0]) foot();
    color("Orange") translate([-gear_center_distance/2,0,foot_height+base_thickness+0.2])
        motor_pinion();
    color("SteelBlue") translate([gear_center_distance/2,0,foot_height+base_thickness+0.2])
        rotate([0,0,180/socket_teeth]) socket_gear();
    for (y=[-32,32])
        color("LightSteelBlue") translate([90,y,0]) waiting_holder();
    // Simplified motor body for visual context only, not a printable motor model.
    color("DimGray") translate([-gear_center_distance/2,0,foot_height-20])
        cylinder(h=20,d=28,$fn=64);
}

if (part=="assembly") assembly();
else if (part=="base") base();
else if (part=="socket_gear") socket_gear();
else if (part=="motor_pinion") motor_pinion();
else if (part=="foot") foot();
else if (part=="waiting_holder") waiting_holder();
else assert(false,"Choose assembly, base, socket_gear, motor_pinion, foot, or waiting_holder.");
