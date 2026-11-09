# Agent's final message

I've written the superseding memo of record (IS-BRAM-2025-07-14 v2). It reverses the earlier memo: Bramwick Commons now **passes** the minimum-load screen, so the disposition is **advance without study agreement**. The countersignature on the earlier memo doesn't prevent this. The procedure (SRP-3 §4) requires the earlier memo to be superseded when a recomputed minimum load disagrees with it.

**What was wrong with the earlier memo**
- **Wrong minimum:** its 1.1 MW is the lowest reading in the whole year — a single 15-minute reading at 03:45 on 03/23/2025. SRP-3 §4 expressly forbids using the overnight minimum and requires the 10:00–16:00 daytime minimum.
- **Wrong data window:** 06/24/2024–06/24/2025 is not the most recent 12 complete calendar months.
- **Wrong cadence:** it used 60-minute intervals, not the required 15. Hourly averaging couldn't produce 1.1 MW anyway; the lowest hourly average in the year is 2,025 kW.
- **Missing items:** no count of intervals evaluated and no application identifier.

**Recomputed on the AMI export**
- **Data:** 07/01/2024–06/30/2025, 35,040 intervals at 15 minutes, with no gaps or duplicates.
- **Daytime window:** 8,760 intervals evaluated, none excluded.
- **Daytime minimum:** 2,400 kW at 11:30 on 02/12/2025.
- **Result:** 1.8 MW ≤ 2.4 MW, a 600 kW margin. The pass holds for any filed capacity up to 2.4 MW.

**Exclusions and robustness**
- The 2,400 kW reading is itself a one-interval dip. No outage, load transfer or switching on ALN-214 appears anywhere in the records, so the procedure gives no basis to exclude it. If it were excluded, the minimum would be 2,418 kW, still a pass.
- Moving the window edge or shifting it an hour for daylight saving doesn't change the minimum, so the result isn't "inconclusive" under SRP-3 §2.

**Before it is filed or sent to the applicant**
- **Signatures:** I left the reviewing-engineer and Meera Vellanki's signature lines blank; I didn't sign for anyone.
- **Missing queue record:** Bramwick Commons doesn't appear in the 07/14/2025 Active or On-Hold queue reports, and no application number exists anywhere on file. The application itself wasn't in the files either, so the 1.8 MW is taken from the earlier memo. The memo asks Queue Administration to confirm both the application number and the 1.8 MW.
- **File actions listed in the memo:**
  - mark the earlier memo superseded and add the cross-reference text to its cover;
  - clear the failed-screen flag on ALN-214;
  - don't send the Study Agreement package;
  - release the hold on the application;
  - file the memo by 07/21/2025.

The memo re-decides only the minimum-load screen (Screen D). The earlier memo decided only that screen and recorded no failure on the other four (A, B, C, E). Several of the inputs needed to evaluate those aren't on file — for example, the interconnection standard sets no penetration threshold and there's no ALN-214 planning study.

The export folder wasn't writable, so the file is at the working-directory root.

Files are in /filesystem:
- Bramwick_Commons_Screen_Memo.docx
