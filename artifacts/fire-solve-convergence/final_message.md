# Agent's final message

I've saved the technical note to `/filesystem/CFDME-2025-041_transient_solve_disposition_revA.docx`. It's 10 pages on the firm letterhead, dated 10/10/2025, with the reviewer and stamp block and the stamp boundary wording. The signature lines and seal are left blank for wet or digital signing. I set it up the usual way: Gordon Selby prepares, authorizes and stamps it, and Marguerite Falk reviews it. Swap the names if that's not right.

**Plateau.** It is the plume's natural puffing, not a numerical problem. With the 3.0 m fire segment, the plume should puff at 0.87 Hz, a 1.15 s period. Mulshi's operator reported a 1.15 s period, also 0.87 Hz. The two agree within 0.41 %. The operator's 1.15 s can't be checked against the log, which doesn't contain enough iterations to show one full cycle. But the three-grid study found 1.14 to 1.15 s on all three grids.

**Steady solution.** None exists for this problem (Modeling Standard §4). Mulshi's three proposals for a fourth attempt are each rejected in the note. Mulshi should not start attempt 4.

**Delivered setup.** Returned for correction. Its physics was copied from the Dry Wash Aerospace high-altitude case, which §7 prohibits. Mulshi's case files and its run log also disagree with each other about what was run. Either way, the following are non-conforming, each with its required replacement in the note:
- solver mode, turbulence model and ambient conditions
- combustion and radiation settings
- the wall assembly treatment and numerical schemes
- the time control and the probe locations

**Authorized run.** The run ceiling (maxDeltaT) is 0.01 s, from our reference dictionary.
- **Write interval:** 0.0461 s. The exact ceiling is 0.046188 s, and rounding up to 0.0462 s would give only 24.99 samples per period.
- **End time:** 31.10 s, which is 8.00 s of startup plus 20 periods. Rounding down to 31.09 s would fall just short of 20 periods.
- **Differences from Mulshi's block:** 9 entries differ: startFrom, endTime, deltaT, adjustTimeStep, writeControl, writeInterval, writePrecision, maxCo and maxDeltaT. As delivered, the write interval would give about one sample per period.

**Mesh and carry-forward.** Attempt 3 ran on Renata's production mesh: 11,214,862 cells, built from geometry revC. Our verification covers only the shared 0.5 m resolution basis (D*/dx 7.52, Pope 0.84) from a separate fluid-only study. It does not cover the production mesh itself, the conjugate wall regions, or the Pope check on this mesh. The geometry, mesh and inlet type carry forward. The inlet keeps Zref 6.10 m and z0 0.03 m, with Uref per case.

Three things to fix before launch:
- **Wind direction (flowDir):** the delivered setting doesn't represent 240°. It should be (0.8660, 0.5000, 0) for 240° and (1, 0, 0) for 270°.
- **Roughness (z0):** 0.03 m isn't in the site met pull, so its source needs recording.
- **Tie refinement:** the mesh log shows the tie embedments refined only 2:1 against the leaves, where §6 requires 4:1.

**Cost.**
- **Projection:** 4 h 28 min per case and 26 h 49 min for the 6 SOW cases. Trevor's "added" 270° direction is already in the SOW, so the matrix stays at six.
- **Basis:** it can't be met. No timed run exists on the production mesh, and the fine study grid is a different mesh, solver setup and core count.
- **Time step:** the fine-grid run was time-step limited at the 0.9 Courant ceiling with no margin, so its step size depends on that mesh. The production mesh has smaller cells near the wall, so its step will be shorter.
- **What the figure is worth:** treat it as a lower bound only, not something to quote or price against. The real figure comes from timing the first authorized case.

**Attempt 3** used 6 h 41 min on 64 cores (424.3 CPU-hours) and produced 0.00 s of simulated time. That is 1.49 times the per-case lower bound. Nothing from it is usable downstream except as supporting evidence for the plateau diagnosis.

The note also flags a conflict inside our own standard: Appendix A says solid properties are held constant, but §3.5 prohibits that. §3.5 should govern, and Appendix A needs correcting.
