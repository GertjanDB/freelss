// A3-mast met twee gleuven en losse punt-houtschroef
//
// De mast staat op de schroef en kan vrij draaien.
// Een A3 (staand, 297 x 420 mm) schuif je met de linkerrand
// in de twee gleuven. De gleuf is een inkeping in de zijkant,
// in de trant van de onderste bevestiging op het voorbeeld.
//
// Test 1 — alleen de gleuven:
//   Schuif de linkerrand ~11 mm diep in beide gleuven.
//   Kijk of het vel blijft zitten of omlaag glijdt.
//
// Test 2 — ponsgat als stop:
//   Pons één gat Ø6 mm (gewone perforator).
//   Hart van het gat: 24 mm vanaf de linkerrand,
//                     38 mm vanaf de bovenrand.
//   Bovenrand van het vel komt dan gelijk met de bovenkant
//   van de mast (2 mm eronder). Onderrand hangt ~48 mm
//   boven de flens, dus vrij van het blad.
//   Steek de arm van de pen van achteren door het gat en laat
//   de steel in de nok achter de mast zakken.
//
// Print (PLA of PETG, laag 0,20 mm):
//   mast-onder / midden / boven  — staand, boring of bus op het bed
//   schroef                       — punt op het bed, draaipen omhoog, met brim
//   pen                           — plat op het bed, met brim
//   4 wanden, mast 20% vulling, schroef 100% (of 6 wanden)
//   Elk mastdeel is 170 mm hoog.
//
// In elkaar:
//   1. Schroef met steeksleutel 13 in hout draaien tot de zeskant
//      op het hout (of op een ring M10) zit.
//      Voorboren: vuren 5,5 mm, harder hout 6 à 6,5 mm, diepte ±50 mm.
//   2. Drie mastdelen op elkaar. Pengaten laten samenvallen
//      (de gleuven wijzen dan dezelfde kant op) en borgen met
//      een stukje 1,75 mm filament van ±35 mm.
//   3. Mast op de draaipen zetten. Hij zakt tot op de flens en draait.
//
// Speling te krap: draaipen licht opschuren.
// Speling te groot: parameter boring_speling verkleinen en opnieuw exporteren.

/* [Export] */
// preview | doorsnede | schroef | mast_onder | mast_midden | mast_boven | mast_enkel | pen
part = "preview";
toon_papier = true;

/* [Mast] */
mast_d = 28;
mast_h = 470;
lichaam = 150;     // zichtbare lengte van deel 1 en 2
tap_l = 20;        // insteekpen tussen de delen
tap_d = 20;
bus_speling = 0.45;

/* [Draaipen] */
draai_d = 10.0;
draai_h = 34;
boring_speling = 0.80;   // diametraal: gat = 10,8 mm
boring_d = draai_d + boring_speling;
boring_h = 40;

/* [Gleuven] */
gleuf_diepte = 11;
gleuf_spleet = 4.0;   // wijd genoeg om een A3-rand erin te duwen
gleuf_r = 22;            // straal van de gebogen inkeping
gleuf1_z = 120;          // hart onderste gleuf
gleuf2_z = 372;          // hart bovenste gleuf
gleuf_recht = 20;        // rechte rug waar de papierrand tegenaan zit

/* [Ponsgat] */
gat_van_links = 24;
gat_van_boven = 38;
pen_z = 430;             // hoogte van de pen-arm = hart van het ponsgat
boss_top = 416;
pen_x_offset = 0;        // extra, normaal 0

/* [Schroef] */
thr_maj = 9.0;
thr_min = 6.0;
thr_pitch = 3.2;
tip_h = 14;
thr_h = 30;
schacht_h = 4;
hex_af = 13;
hex_h = 12;          // hoog genoeg voor een steeksleutel 13
nek_schroef = 2;     // vrije rand boven de zeskant
kegel_h = 10;        // 45°+ zodat de flens zonder support print (punt op het bed)
lip_h = 2.5;
flens_d = 34;

/* [Pen] */
d_arm = 5.0;             // past door ponsgat Ø6
d_steel = 4.8;           // zakt in de nok
d_nek = 6.2;             // blijft op de rand van de nok liggen
steel_l = 14;
arm_voor = 9;            // hoe ver de arm vóór het papier uitsteekt
pen_y = -12;             // nok en steel zitten achter het papier

/* [Verborgen] */
fn_mast = 96;
pengat_d = 3.0;
pengat_y = -4;           // uit het midden, zodat het maar op één manier past

// ——— afgeleide maten ———
mast_r = mast_d / 2;
bus_d = tap_d + bus_speling;
rand_x = mast_r - gleuf_diepte;
pen_x = rand_x + gat_van_links + pen_x_offset;
papier_boven = pen_z + gat_van_boven;
papier_onder = papier_boven - 420;
nek_l = pen_z - boss_top;
arm_l = arm_voor - pen_y;

flens_top = tip_h + thr_h + schacht_h + hex_h + nek_schroef + kegel_h + lip_h;

echo("papier boven", papier_boven, "onder", papier_onder);
echo("papierrand x", rand_x, "ponsgat x", pen_x, "z", pen_z);
echo("boring", boring_d, "bus", bus_d);

module pinhole(z) {
  translate([0, pengat_y, z])
    rotate([90, 0, 0])
      cylinder(h = mast_d + 8, d = pengat_d, center = true, $fn = 24);
}

module gleuf_op(z) {
  // Gebogen mond, zoals de inkeping onderaan het voorbeeld,
  // met een rechte rug zodat een rechte A3-rand vlak aanligt.
  translate([mast_r - gleuf_diepte + gleuf_r, 0, z])
    rotate([90, 0, 0])
      cylinder(h = gleuf_spleet, r = gleuf_r, center = true, $fn = 120);
  translate([mast_r - gleuf_diepte, -gleuf_spleet / 2, z - gleuf_recht / 2])
    cube([gleuf_diepte + 3, gleuf_spleet, gleuf_recht]);
  // Iets wijdere invoer in de buitenste 3 mm, zodat de rand de gleuf vindt.
  intersection() {
    translate([mast_r - 3.2, -(gleuf_spleet + 2.2) / 2, z - gleuf_r])
      cube([7, gleuf_spleet + 2.2, gleuf_r * 2]);
    translate([mast_r - gleuf_diepte + gleuf_r + 1.5, 0, z])
      rotate([90, 0, 0])
        cylinder(h = gleuf_spleet + 2.4, r = gleuf_r - 3, center = true, $fn = 80);
  }
}

module boring() {
  translate([0, 0, -0.2])
    cylinder(h = 2.4, d1 = boring_d + 5, d2 = boring_d, $fn = 64);
  translate([0, 0, 2.0])
    cylinder(h = boring_h - 2.0, d = boring_d, $fn = 64);
  translate([0, 0, boring_h - 0.05])
    cylinder(h = boring_d / 2 + 0.2, d1 = boring_d, d2 = 0.4, $fn = 48);
}

module bus() {
  translate([0, 0, -0.2])
    cylinder(h = 2.6, d1 = bus_d + 4, d2 = bus_d, $fn = 64);
  translate([0, 0, 2.2])
    cylinder(h = tap_l - 2.2 + 0.8, d = bus_d, $fn = 64);
  translate([0, 0, tap_l + 0.6])
    cylinder(h = bus_d / 2, d1 = bus_d, d2 = 0.4, $fn = 48);
}

module tap_op(z) {
  translate([0, 0, z]) {
    cylinder(h = tap_l - 1.3, d = tap_d, $fn = 64);
    translate([0, 0, tap_l - 1.3])
      cylinder(h = 1.3, d1 = tap_d, d2 = tap_d - 2.4, $fn = 64);
  }
  // Schuine overgang naar het lichaam, tegen een scherpe kerf.
  translate([0, 0, z - 1.5])
    cylinder(h = 1.5, d1 = tap_d + 3, d2 = tap_d, $fn = 64);
}

module draagvlak() {
  // Alleen de buitenring raakt de flens, dan draait hij lichter.
  translate([0, 0, -0.05])
    cylinder(h = 0.85, d = mast_d - 8, $fn = fn_mast);
}

module nok() {
  // Massief achter de mast. Onderkant loopt steil genoeg om zonder support te printen.
  hull() {
    translate([mast_r - 3.2, pen_y + 1.2, boss_top - 52])
      cube([4.0, 6.0, 46]);
    translate([pen_x, pen_y, boss_top - 22])
      cylinder(h = 22, d = 14, $fn = 48);
  }
}

module nok_gat() {
  translate([pen_x, pen_y, boss_top - steel_l - 1.5])
    cylinder(h = steel_l + 1.6, d = 5.25, $fn = 36);
  translate([pen_x, pen_y, boss_top - 1.4])
    cylinder(h = 1.8, d1 = 5.25, d2 = 8.2, $fn = 36);
}

module mast_onder() {
  difference() {
    union() {
      cylinder(h = lichaam, d = mast_d, $fn = fn_mast);
      tap_op(lichaam);
    }
    boring();
    gleuf_op(gleuf1_z);
    pinhole(lichaam + tap_l / 2);
    draagvlak();
  }
}

module mast_midden() {
  translate([0, 0, -lichaam])
    difference() {
      union() {
        translate([0, 0, lichaam])
          cylinder(h = lichaam, d = mast_d, $fn = fn_mast);
        tap_op(lichaam * 2);
      }
      translate([0, 0, lichaam])
        bus();
      pinhole(lichaam + tap_l / 2);
      pinhole(lichaam * 2 + tap_l / 2);
    }
}

module mast_enkel() {
  difference() {
    union() {
      cylinder(h = mast_h, d = mast_d, $fn = fn_mast);
      nok();
    }
    boring();
    gleuf_op(gleuf1_z);
    gleuf_op(gleuf2_z);
    nok_gat();
    draagvlak();
    translate([0, 0, mast_h - 1.3])
      difference() {
        cylinder(h = 2, d = mast_d + 2, $fn = fn_mast);
        translate([0, 0, -0.1])
          cylinder(h = 1.5, d1 = mast_d, d2 = mast_d - 2.6, $fn = fn_mast);
      }
  }
}

module mast_boven() {
  translate([0, 0, -(lichaam * 2)])
    difference() {
      union() {
        translate([0, 0, lichaam * 2])
          cylinder(h = mast_h - lichaam * 2, d = mast_d, $fn = fn_mast);
        nok();
      }
      translate([0, 0, lichaam * 2])
        bus();
      // Zachte bovenrand.
      translate([0, 0, mast_h - 1.3])
        difference() {
          cylinder(h = 2, d = mast_d + 2, $fn = fn_mast);
          translate([0, 0, -0.1])
            cylinder(h = 1.5, d1 = mast_d, d2 = mast_d - 2.6, $fn = fn_mast);
        }
      pinhole(lichaam * 2 + tap_l / 2);
      gleuf_op(gleuf2_z);
      nok_gat();
    }
}

// ——— schroef ———

module tandprofiel(pitch, hoogte) {
  polygon([
    [0, -pitch * 0.40],
    [hoogte, -pitch * 0.10],
    [hoogte,  pitch * 0.10],
    [0,  pitch * 0.40]
  ]);
}

module hout_draad(lengte, d_min, d_maj, pitch, fijn) {
  hoogte = (d_maj - d_min) / 2;
  windingen = lengte / pitch;
  cylinder(h = lengte, d = d_min, $fn = 48);
  linear_extrude(height = lengte,
                  twist = -360 * windingen,
                  slices = max(3, round(windingen * (fijn ? 28 : 14))),
                  convexity = 12)
    translate([d_min / 2 - 0.35, 0])
      tandprofiel(pitch, hoogte + 0.35);
}

module schroef_draad(fijn) {
  totaal = tip_h + thr_h;
  intersection() {
    hout_draad(totaal + thr_pitch, thr_min, thr_maj, thr_pitch, fijn);
    union() {
      cylinder(h = tip_h, d1 = 1.6, d2 = thr_maj + 0.8, $fn = 48);
      translate([0, 0, tip_h - 0.15])
        cylinder(h = thr_h + thr_pitch, d = thr_maj + 0.8, $fn = 48);
    }
  }
}

module zeskant(h, af) {
  rotate([0, 0, 30])
    cylinder(h = h, d = af / cos(30), $fn = 6);
}

module schroef(fijn = true) {
  schroef_draad(fijn);
  // Gladde schacht voor een optionele ring M10.
  translate([0, 0, tip_h + thr_h - 0.05])
    cylinder(h = schacht_h + 0.05, d = 9.3, $fn = 48);
  translate([0, 0, tip_h + thr_h + schacht_h])
    zeskant(hex_h, hex_af);
  translate([0, 0, tip_h + thr_h + schacht_h + hex_h])
    cylinder(h = nek_schroef, d = 15.2, $fn = 48);
  // Kegel loopt uit onder ~48°, printbaar met de punt op het bed.
  translate([0, 0, tip_h + thr_h + schacht_h + hex_h + nek_schroef - 0.05])
    cylinder(h = kegel_h + 0.05, d1 = 16, d2 = flens_d, $fn = 80);
  translate([0, 0, tip_h + thr_h + schacht_h + hex_h + nek_schroef + kegel_h])
    cylinder(h = lip_h, d = flens_d, $fn = 80);
  // Draaipen. Wortel iets dunner zodat de hoek niet in de boring klemt.
  translate([0, 0, flens_top])
    cylinder(h = 1.0, d1 = draai_d - 1.8, d2 = draai_d, $fn = 64);
  translate([0, 0, flens_top + 1.0])
    cylinder(h = draai_h - 1.0 - 1.6, d = draai_d, $fn = 64);
  translate([0, 0, flens_top + draai_h - 1.6])
    cylinder(h = 1.6, d1 = draai_d, d2 = draai_d - 2.6, $fn = 64);
}

// ——— losse pen ———
// Canoniek: steel vanaf z=0 omhoog, arm vanaf de elleboog langs +Y.

module pen_solid() {
  cylinder(h = steel_l, d = d_steel, $fn = 32);
  translate([0, 0, steel_l - 0.15])
    cylinder(h = nek_l + 0.15, d = d_nek, $fn = 32);
  translate([0, 0, steel_l + nek_l])
    sphere(d = d_nek, $fn = 32);
  translate([0, 0, steel_l + nek_l])
    rotate([-90, 0, 0])
      cylinder(h = arm_l, d = d_arm, $fn = 32);
  translate([0, arm_l, steel_l + nek_l])
    sphere(d = d_arm, $fn = 32);
}

module pen_geplaatst() {
  translate([pen_x, pen_y, boss_top - steel_l])
    pen_solid();
}

// Plat op het bed: dikke nek krijgt een klein vlak, steel blijft rond.
module pen_print() {
  zc = d_steel / 2;
  intersection() {
    translate([0, 0, zc])
      rotate([0, 90, 0])
        pen_solid();
    translate([-2, -2, 0])
      cube([80, 80, 20]);
  }
}

// ——— samenstelling voor het voorbeeld ———

module mast_samen() {
  mast_onder();
  translate([0, 0, lichaam])
    mast_midden();
  translate([0, 0, lichaam * 2])
    mast_boven();
}

module papier() {
  color([0.94, 0.90, 0.74, 0.72])
    difference() {
      translate([rand_x, -0.25, papier_onder])
        cube([297, 0.5, 420]);
      translate([pen_x, 0, pen_z])
        rotate([90, 0, 0])
          cylinder(h = 6, d = 6, center = true, $fn = 32);
    }
}

module samenstelling(met_papier = true) {
  color([0.62, 0.64, 0.66])
    translate([0, 0, -flens_top])
      schroef(false);
  color([0.48, 0.30, 0.18])
    mast_samen();
  color([0.40, 0.24, 0.14])
    pen_geplaatst();
  if (met_papier && toon_papier)
    papier();
  // Blad: de zeskant komt net boven het hout uit.
  color([0.50, 0.33, 0.16])
    translate([0, 0, tip_h + thr_h + schacht_h - flens_top - 8])
      difference() {
        cylinder(h = 8, d = 130, $fn = 80);
        translate([0, 0, -0.2])
          cylinder(h = 9, d = 12, $fn = 40);
      }
}

if (part == "schroef")
  schroef(true);
else if (part == "mast_onder")
  mast_onder();
else if (part == "mast_midden")
  mast_midden();
else if (part == "mast_boven")
  mast_boven();
else if (part == "mast_enkel")
  mast_enkel();
else if (part == "pen")
  pen_print();
else if (part == "doorsnede")
  difference() {
    samenstelling(true);
    translate([0, 0.02, -90])
      cube([420, 220, 680]);
  }
else if (part == "detail_gleuf")
  intersection() {
    mast_onder();
    translate([-4, -24, 96])
      cube([36, 48, 52]);
  }
else if (part == "detail_pen")
  intersection() {
    samenstelling(true);
    translate([-8, -40, 340])
      cube([80, 80, 140]);
  }
else
  samenstelling(true);
