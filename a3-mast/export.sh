#!/bin/sh
# Exporteert de printbare STL's. Vereist OpenSCAD.
set -e
cd "$(dirname "$0")"
run() {
  part=$1
  out=$2
  echo "== $out"
  openscad -o "$out" --export-format=binstl -D "part=\"$part\"" a3-mast.scad
}
run schroef schroef.stl
run mast_onder mast-onder.stl
run mast_midden mast-midden.stl
run mast_boven mast-boven.stl
run mast_enkel mast-enkel.stl
run pen pen.stl
echo "Klaar."
