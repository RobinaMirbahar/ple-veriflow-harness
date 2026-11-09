# Agent's final message

The memo says Permission to Operate **cannot issue on 08/04/2025** and tells Lena to hold it. It is saved as `/filesystem/Corwyn_PTO_Memo.docx` (5 pages), and I opened one work package, #47, for the site in the DER Program Backlog Review project.

**Why it can't issue.** The ISA keeps the POI recloser open at all times before Permission to Operate, except for the witness test (§6.1). With the recloser open, the site cannot have the live telemetry that TCS-02 §5 requires at the moment of issue:
- **The RTU has no power.** Corwyn feeds it from its own PV switchboard, behind the recloser. The recloser has been open since 15:35 on 07/08, so the RTU has had only its UPS since then. On the contractor's own 5.5-hour figure, it went dark around 21:05 that evening. The memo asks Lena to check her SCADA display for this.
- **The inverters can't report.** They take their control power from their own ac output, so the per-inverter data the RTU must present is also dead.
- **The ISA allows no early energization.** Unlike the Halbray ISA, Corwyn's has no term letting the Company energize the site before Permission to Operate.
- **The SOC confirmation on the checklist doesn't count.** It is dated 07/08, the witness-test day, when the recloser was closed. TCS-02 §5 requires the confirmation when Permission to Operate is requested and issued.

**What has to be done, and by whom:**
- **Corwyn Realty Partners (through Brantley Electric):** power the RTU from a source that doesn't depend on the recloser. Their own monitoring cabinet is already fed that way, from an office-building panel. They must also show the UPS lasts at least 4 hours at the actual load. The 5.5-hour claim isn't supported: on SCADA/EMS's own figures for its standard kit, the UPS would give about 3.1 hours after derating. This is new work needing a City of Wrenford permit and final approval. Not achievable by 08/04.
- **Corwyn and DER Program Office Contracts:** amend the ISA so the site can be energized before Permission to Operate with the inverters disabled. It isn't a capacity or interconnection-point change, so an ordinary written amendment is enough. Without it, the SOC can never confirm telemetry for this site. It could be signed in time, but Permission to Operate would still wait on the RTU supply.
- **SCADA/EMS Engineering:** specify the new supply point in the RTU installation drawing, state the enclosure load, and confirm the RTU runs on the new supply.
- **Distribution Operations:** do the switching for the early energization once the amendment is signed.
- **Commissioning (S. Rennick):** correct the checklist, which has no line for the RTU's power supply.
- **The Office:** reply to Corwyn's 07/10 letter.

Apart from the four matters under separate review, everything else on the record is in order. That covers the witness test, the City's final approval, the revenue meter, and the inverter listing and certificate.

The work package records the determination, the basis, and all of the items above with owners, including Corwyn's two. It is assigned to S. Rennick at High priority, with Lena and Marcus Deele as watchers. Dates are 07/14 to 08/15/2025, matching the other backlog items.

Things I chose that you may want to change:
- The memo's document number (DPO-PTO-0629-01) is my own; nothing on record set one.
- The P.E.'s name, licence number, signature and date are left blank for the reviewing engineer to fill in.
- The UPS check assumes the "1.5 kVA online UPS" is the Corvane OL-1500R, the only such data sheet on file.
