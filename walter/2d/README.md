# Walter 2D for Laser Cut / Housing Prototyping

This folder contains 2D vector files (in mm scale) to assist with laser cutting, CNC routing, or general housing design for the Walter module.

Included files represent the board’s physical outline and can be used to:
- Cut a mounting area or clearance in enclosures
- Add alignment or anchor features for Walter
- Integrate Walter into panel layouts or case designs

## Notes for Use
- All dimensions are in **millimeters (mm)**.
- Files are provided as **vector formats** (`.svg`, `.pdf`, `.dxf`) and should open in most CAD, vector, or laser software.
- You may need to adjust **cut/engrave/stroke settings** depending on your machine or fabrication provider.
  - Red hairlines (0.001 pt) are commonly used for cuts
  - Black fills or blue lines are typically used for engraving
- Always check alignment and scaling before running a final job.

## Related Footprint Info
Walter uses 2.54mm pitch headers with 14 pins per side (see `footprint/README.md` for full part details). The 2D outline does **not** include pin depths or socket clearance—verify fit based on your exact setup.
