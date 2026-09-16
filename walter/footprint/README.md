# Walter footprint

Walter uses 2.54mm pin headers with 14 pins on each side. The mounted part is 
Würth Elektronik 61001418221 with a 6mm pin height or a compatible part with 
slightly less high pins.

Walter can be soldered directly onto your design using wave soldering or by
making use of matching sockets. Possible sockets to use are:
 -  Würth Elektronik 61301411821
 -  Multicomp Pro 2212S-14SG-85
 -  Samtec SSW-114-01-T-S

## Altium Designer
Altium designer footprints and schematics symbols are also available. The 3D models for the sockets are intentionally left out to avoid potential licensing issues. You can import the 3D/ STEP Models in Altium before placing the components. The 3D model for walter is placed with enough standoff height to accomodate Samtec SSW-114-01-T-S sockets.
### Usage
1. Download the .schlib and .pcblib files (and move them to your PCB project folder).
2. Use the "Add Existing to Project" option in Altium Designer and add both the files to your project. 
3. Place the Schematic symbol from the  Schematic library (which can be found in ```Libraries/Schematic Library Documents``` under your Altium Designer Project)
