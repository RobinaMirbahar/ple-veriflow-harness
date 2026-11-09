I've written `output/submission.zip` with all five files: `takeoff.csv`, `locations.csv`, `bom.csv`, `register.csv` and `basis.md`. My own checks pass: extended prices equal quantity × rate, purchases are whole cartons and cover required + 5%, unit prices match between bill rows, and the condition counts in `locations.csv` match `bom.csv`. None of that confirms the counts against the grader. Several calls below are judgement calls, and a wrong one would fail a hard clause.

**How I counted.** I matched every symbol on the plans against the 17 symbols in the E-001 legend, then placed each one on the hall floor grid using the tile lines printed on each sheet.
- **Match lines:** devices past a match line are drawn grey on that sheet and black on the sheet that schedules them, so each is counted once. The background shading does not follow the match lines; I used the lines.
- **Enlarged plans:** all 14 frames on E-231 to E-233 are counted, with no device appearing in two frames.
- **ADD-02:** the 4 duplex receptacles (R1) inside the revision-2 cloud on E-201 are deleted. Two quadraplex receptacles (R2) go in at the two southernmost positions.
- **Keyed notes** (not drawn, each counted once although they repeat across sheets):
  - visible appliances (F1): 8 for the north and south wall bays plus 4 for the exit doors.
  - weather-resistant receptacles (R5): 28, one per CRAH unit. A-101, M-101 and A-102 all show 4 perimeter plus 24 in-row units. The A-601 and M-101 schedules still say 16, but they predate the in-row units added in revision 2.
  - floor boxes (R7): 6, one per PDU.
- **Unresolved:** a square-with-diamond symbol on E-232 (bay A4) and E-233 (bay C4) is not in the legend. It carries no quantity and is listed in the basis.
- **Zero:** R8 and F6 have no instances.

**Totals:** 242 devices. R1 51, R2 8, R3 8, R4 6, R5 32, R6 4, R7 6, J1 38, P1 7, F1 12, F2 4, F3 3, F4 6, F5 30, D1 27.

**Basket total: $18,168.14.** I priced at each price-list line's own quantity breaks, as section 4.3 and the price list say, not the generic 1–24 / 25–99 / 100+ bands in E-20. Eight lines would price differently under those bands.

**Calls a grader could read differently:**
- **Pull box on E-201 at (2.40 m, 0.90 m):** it sits exactly on the edge of a CRAH condensate apron and is equidistant from two walls. I carried it as DAMP. If the edge doesn't count as inside, it would be RATED-2HR or DRY-MASONRY.
- **Four R5s on E-201** inside the Electrical/Entry strip, which should be drawn empty: I counted them because they appear on no enlarged plan.
- **Under-floor detectors (F5):** drawn with a coarser dash than the legend swatch. I treated them as F5, because their layout matches the spec's 21 m² per detector.
- **Assemblies:**
  - DAMP gets only the wet-listed GFCI receptacle, because no damp-listed box is in the catalogue. The while-in-use hood is stated in the basis with no line.
  - RATED-2HR and EMERGENCY get a box but no plaster ring.
  - Junction boxes get a 4 in box and blank cover, no ring.
  - Pull boxes are the pull box alone.
  - Duct detectors are installation only, plus a 4 in box.
- **Keynote devices in `locations.csv`:** the F1s are filed under E-211. The R5s and R7s go to the E-201 to E-204 sheet covering each CRAH or PDU.