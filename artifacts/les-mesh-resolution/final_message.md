# Agent's final message

I've written the note: `/filesystem/CFDME-2025-041_resolution_note_revA.docx` (about 2¼ pages). Item 4 can't close on what's on file as it stands, but it can close without running anything new.

**Where the index lands:** about 30, well outside the 5–10 band. The report rests on the fine grid of the three-grid study. On that grid the area around the fire is refined two levels below the 0.5 m background, so its cells are 0.125 m; the mesh check output agrees. With the plume length scale of 3.76 m that the report carries, 3.76 / 0.125 = 30.1. That is about three times the top of the band, meaning the mesh is finer than the band asks for, not coarser. The 7.5 in rev B divides by the 0.5 m background cell, which only exists outside the fire region. Also, the scoping memo's own inputs give 3.74 m, not 3.76 m; it's a small arithmetic slip that doesn't change anything.

**What acceptance rests on:** with the index out of band, it rests on the resolved-energy criterion alone. That is 84 % at one probe, 4 points over the 80 % threshold. Our standard accepts either criterion on its own, but three things need Marguerite's decision:
- **One criterion or both:** the standard expects both for life-safety work, and this report backs a public fire-performance claim for houses. If both are required, she has to either record the index of about 30 as a deviation or leave it as a failure.
- **Is the 84 % enough:** it comes from one probe, the averaging window isn't stated, and the data behind it isn't on the server.
- **Basis for the plume length scale:** the 3.76 m and the 7.5 come from the 10/08 scoping memo, which she concurred. Changing them means revising that memo, not just the report.

**Where the 84 % was taken:** on the plume axis about 2.8 m above the source, in the 0.125 m cells, not in the 0.5 m cells the reported 7.5 describes. Measured in the same region, the result is: resolved-energy criterion met, index above the band. The size of the refined zone isn't recorded anywhere. I worked out that it contains the probe from its cell counts, and the note says so.

**Ambient values:** they don't represent the site. They are sea-level air at 20 °C; the site is at about 750 m with a design ambient of 35–42 °C.
- At site pressure the plume length scale rises about 3.6 %, to 3.88 m.
- Ambient temperature cancels out of the formula, and humidity changes it by less than 0.2 %.
- The index becomes about 31, further from the band, so no conclusion changes.
- The note warns against plugging in the site temperature while keeping the sea-level density, which would wrongly shrink it.

**What would settle it:**
1. A rev C Verification section that states all the required values in the body, with the correct cell size, and says plainly that the index is above the band.
2. Marguerite's three decisions, recorded against item 4.
3. Renata files the existing output behind the 84 % (averaged values at the probe and the averaging window). If she can't produce it, the item stays open unless Marguerite accepts a one-line entry on its own.

**Also in the note:**
- The 750 m elevation comes from the wind-load basis memo. The weather data has no pressure, so I used the standard-atmosphere value for that height.
- The study's figures don't carry over to the production mesh, which isn't built the way the report's Appendix C says. Its only run on file is steady RANS, which can't give a resolved-energy figure at all. That belongs mainly to checklist items 2–3.

The From and Date lines are left blank for you to fill in.
