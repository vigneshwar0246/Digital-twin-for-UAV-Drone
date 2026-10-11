# AERION: beginner's demonstration script

Use this as a click-by-click rehearsal guide for the engineering fallback demonstration. The historical live-candidate research workflow and release-gate warning are covered in [DEMO_GUIDE.md](DEMO_GUIDE.md). The separate 95.28% result belongs only to the simulator-scenario classifier; see the [model evaluation guide](backend/model_evaluation/README.md). The workspace opens with the **2D engine cutaway**; engineering faults produce component highlights, and the optional **3D engine** button remains available.

## 1. Understand what you are presenting

Say: “AERION is a digital representation of an aircraft engine. It receives engine measurements, checks their quality, assesses engine condition, and shows diagnostic evidence on the engine visualization.”

Remember these meanings:

| Term on screen | Plain meaning |
|---|---|
| RPM | How fast the engine rotates |
| CHT | Cylinder head temperature |
| EGT | Exhaust gas temperature |
| Oil pressure | Pressure supporting lubrication |
| Vibration | A scalar measurement of shaking |
| Health index | A prototype condition score out of 100 |
| Engineering/anomaly score | Strength of diagnostic evidence; it is not a failure probability |
| RUL | Remaining useful life, shown here as an engineering estimate |
| Replay | Reviewing earlier recorded samples |
| Seed | A number used to reproduce generated mission behavior |

This project demonstrates generated engine behavior. By default, diagnostics use engineering rules and statistics. A separately labelled trained classifier can be enabled explicitly for research, but it fails the release gate and its score is uncalibrated. Say “the system detects evidence of a fault,” rather than “it predicts an exact failure date.”

## 2. Start everything before presenting

1. Open a PowerShell terminal in `D:\projects D\aircraft`.
2. Run ` .\run_project.bat `.
3. Leave this terminal running throughout the presentation.
4. Open `http://127.0.0.1:5173` in the browser.
5. Keep `http://127.0.0.1:5173/twin` bookmarked as a direct workspace shortcut.
6. The launcher enables local dataset-demo mode, which normally does not require sign-in.

Avoid refreshing the browser during a recorded demonstration: the frontend recording is held in memory. Export it before refreshing or starting another demo.

## 3. Opening aircraft page: 30–45 seconds

1. Scroll slowly downward until the aircraft settles.
2. Click **INITIALIZE DIGITAL TWIN**.
3. Scroll farther down to the engine close-up.
4. Click **ENTER**.

Say: “We start with the aircraft, then move into its engine digital twin.”

If scrolling confuses you during rehearsal, open `/twin` directly. The aircraft introduction is visual navigation; it is not a fault simulation control.

## 4. Know the two simulation buttons before changing values

Open **Mission Simulation** in the left sidebar.

| Button | What it does | Which fields matter |
|---|---|---|
| **Start demo** | Generates interactive demo telemetry and submits it to the backend diagnostic processor | Throttle, load, altitude, temperature, duration, seed, scenario |
| **Run backend simulation** | Generates a complete backend mission and starts playback | Scenario mapping, duration, seed; custom throttle/load/altitude/temperature fields above are not submitted |

The second button is below the heading **Run existing backend mission model**. Do not accidentally use it when following a **Start demo** recipe.

**Speed** changes playback time. Judge progress by the seconds counter, not by a fixed wall-clock wait: request latency can slow an interactive demo.

**Pause** freezes playback. **Pause chart** only freezes that chart. **Stop** stops playback; it does not repair a fault. **Reset** clears the current recording. **Start demo** starts a new recording. **Reset view** only resets engine pan/zoom and selection.

## 5. Show a healthy baseline first: about one minute

Use this route because “Normal Operation” in the interactive demo can still accumulate sensor warnings from constant or missing channels.

1. In **Mission Simulation**, choose **Normal Operation**.
2. Set **Duration (s)** to `180`.
3. Set **Random seed** to `26054`.
4. Set **Speed** to `1`.
5. Click **Run backend simulation**.
6. Once frames load, click **Pause** in the top status bar.
7. Open **Mission Replay**.
8. Click **Open current recording**.
9. Drag **Replay timeline** fully left. This selects frame 1, the start of the recorded mission.
10. Open **Live Digital Twin** without changing the Data Source dropdown.

Expected: the baseline frame has no active diagnostic faults and no fault highlight. In a direct backend check of this configuration, the first eight samples had no active diagnostics. This is an early mission baseline, not a claim that every later sample is fault-free.

Say: “This sample is our baseline. The engine view is neutral because the backend has not activated a fault diagnosis.”

Do not demand a health value of exactly 100. A prototype health score and the presence of an active diagnosis are different outputs.

## 6. First dependable fault: lubrication

Go to **Mission Simulation** and enter all these values:

| Field | Value |
|---|---:|
| Throttle (%) | 45 |
| Engine load (%) | 30 |
| Altitude (m) | 1500 |
| Ambient temperature (°C) | 15 |
| Duration (s) | 180 |
| Random seed | 26054 |
| Scenario / fault injection | Oil Pressure Drop |
| Speed | 2 |

1. Click **Start demo**.
2. Watch the seconds counter. Let it reach approximately `40–60 s`.
3. Look for **LUBRICATION** beneath the engine. The oil-pressure value should have fallen substantially.
4. Click **Pause** in the top bar.
5. Click the **LUBRICATION** fault button beneath the engine.
6. Observe the oil-area highlight and score/uncertainty label.
7. Click **Reset view** to return to the full engine.
8. Open **Live Digital Twin**; retain the Simulation data source.
9. In the diagnostic card, click **Contributing evidence** and point to oil-pressure/temperature evidence.

Say: “The scenario changes measurements. The backend then detects lubrication evidence. The colored area links that evidence to the conceptual oil system.”

An in-memory check using these values and half-second samples reached `LUBRICATION_ISSUE` by the final 60-second sample. Additional `SENSOR_DRIFT` evidence can appear because some demo channels remain constant or absent. Actual activation timing depends on the sample window.

## 7. Other useful fault demonstrations

For each row: return to **Mission Simulation**, retain the six numeric values from section 6, change only **Scenario / fault injection**, then click **Start demo**. Let the counter reach approximately `60 s`, pause, and inspect the actual fault buttons. Save/export the previous recording first if you want to retain it.

| Scenario to choose | What to inspect | Diagnoses observed in the 60-second processor check |
|---|---|---|
| **Abnormal Vibration** | Vibration metric and rotating/engine region highlight | Abnormal Vibration; additional Sensor Drift |
| **Misfire** | Cylinder EGT imbalance and cylinder-region highlight | Misfire, Combustion Instability; additional Sensor Drift |
| **Injector Degradation** | Fuel flow and cylinder EGT imbalance | Fuel Injector Degradation, Misfire, Combustion Instability; additional Sensor Drift |
| **Sensor Drift** | Sensor-region highlight and contributing evidence | Sensor Drift |

Suggested narration:

- Vibration: “We increased the vibration measurement; the backend identifies abnormal vibration evidence.”
- Misfire: “An imbalance between cylinder readings activates ignition/combustion-related hypotheses.”
- Injector: “Fuel-system and combustion symptoms can overlap, so several hypotheses may be active together.”
- Sensor drift: “A sensor warning asks us to assess measurement reliability. It does not prove mechanical damage.”

Do not say a specific cylinder has failed unless the diagnostic explicitly identifies it. Current outputs often localize only to a subsystem.

## 8. All eleven categories: what you can actually demonstrate

Supporting a diagnostic category does not mean the current scenario dropdown can independently force it. Present this distinction honestly.

| Category | Current demonstration route |
|---|---|
| Misfire | Use **Misfire** interactive recipe above |
| Fuel Injector Degradation | Use **Injector Degradation** interactive recipe above |
| Cooling System Degradation | **Cylinder Overheating** exercises thermal telemetry, but does not reliably activate this diagnosis at the section 6 values |
| Lubrication Issue | Use **Oil Pressure Drop** interactive recipe |
| Sensor Drift | Use **Sensor Drift**; constant demo channels can also produce it in other scenarios |
| Sensor Failure | No dedicated UI scenario. Missing required fields in the strict telemetry API are rejected; they are not automatically displayed as a failure diagnosis |
| Combustion Instability | Appeared with **Misfire** and **Injector Degradation** |
| Overheating | **Cylinder Overheating** does not guarantee activation. Do not promise an overheating warning from the dropdown alone |
| Abnormal Vibration | Use **Abnormal Vibration** interactive recipe |
| Battery/Alternator Abnormality | **Alternator Degradation** changes voltage, but did not activate this diagnosis in the checked recipe |
| Injection Timing Abnormality | No dedicated UI scenario or direct injection-timing field |

For the last group, say: “These categories exist in the diagnostic engine and visualization mapping. The current demo controls do not provide a verified independent trigger for every category.”

Do not use screenshot/test fixtures to claim live detection. A complete eleven-category live presentation requires additional prepared, validated telemetry sequences; this guide does not invent controls or guaranteed results.

Avoid increasing throttle to 100 just to force a fault. The interactive formula can exceed the backend RPM limit; the result may be a validation error rather than a diagnosis. Stay with the documented values during the presentation.

## 9. Page-by-page tour after pausing a fault

Keep the paused faulty frame while opening these sidebar pages. Navigation normally keeps the current data; changing the Data Source dropdown can clear or replace it.

| Page | Exact action | What to explain |
|---|---|---|
| **Overview** | Inspect Health, RUL, Anomaly Score, Active Faults | A summary of the same current sample |
| **Live Digital Twin** | Click a fault button; click **Focus component** in a card; click **Reset view** | A simple highlight connects the diagnosis to an engine region |
| **Engine Telemetry** | In **Chart parameter**, choose **Oil pressure** or **Vibration RMS** | Measurements and quality flags provide the evidence; a dash means unavailable |
| **Health Monitoring** | Read subsystem bars and cylinder values | Which subsystem condition scores changed |
| **AI Diagnostics** | Expand **Contributing evidence**; optionally click **Acknowledge** | Evidence and recommended actions; acknowledgment is local and does not clear the fault |
| **RUL & Degradation** | Compare current health and recorded start health | Remaining life is a prototype estimate, not a certified service-life promise |
| **Mission Simulation** | Use the tested recipes above | Controlled telemetry changes go through backend diagnostics |
| **Mission Replay** | **Open current recording**, seek, **Play**, **Pause** | Review a before/after sequence |
| **Performance Maps** | Inspect **RPM vs fuel flow** | This is an observed trajectory, not a manufacturer engine map |
| **Maintenance** | Change the action dropdown to **Assigned for review**; type a note | A session-local inspection worklist |
| **Reports** | Click **Export JSON**, **Export CSV**, or **Print / PDF** | Export the current buffered recording |
| **Fleet Health** | Inspect the observed-engine card | Only the current engine is listed; no complete fleet inventory API exists |
| **Data / CAN Monitor** | Click **Fetch backend data** | Adapter health; no verified physical bus is connected by default |
| **System Configuration** | Inspect the pipeline; use **Open live dataset twin** when ready | Reconnect to the bundled dataset feed |
| **Why It Matters** | Scroll through the explanatory page | The use case and motivation; this is not a simulation control page |

On **AI Diagnostics**, clicking **Fetch backend data** in “ML evaluation / release status” retrieves the offline model report. Expect a failed release gate / not-release-ready status. Explain: “The offline classifier is still under evaluation. The current visual diagnostics come from the live engineering/statistical processor.”

## 10. Replay the fault from its start

1. Pause the interactive fault demo.
2. Open **Mission Replay**.
3. Click **Open current recording**.
4. Drag **Replay timeline** left to the first frame.
5. Drag it right to a late frame and compare values/highlights.
6. Select **Replay speed** `2` and click **Play**.
7. Click **Pause** at a useful faulty frame.

The first frame of an interactive demo is not guaranteed to be entirely fault-free. Use the explicit backend baseline in section 5 when you need a verified no-diagnostics comparison.

**Fault events** is a shortcut list, not an exhaustive audit of every secondary diagnosis. Seeking changes the displayed sample; it does not repair the engine.

For historical data: **Load backend missions** → expand **Available missions** → enter `MISSION_0110` in **Mission ID** → **Open mission**. The historical replay and **Reports** recording buffer are not automatically the same dataset. For a dependable export in this presentation, use **Open current recording** from your own simulation/demo.

## 11. Finish with an exported report

1. With your demo recording still present, open **Reports**.
2. Point to sample count, maximum temperatures, peak vibration, health before/after, and faults.
3. Click **Export JSON** to download `mission-report.json`.
4. Optionally click **Export CSV** to download `mission-telemetry.csv`.
5. For a PDF, click **Print / PDF** and choose your browser's **Save as PDF** destination.

Say: “The recording lets an engineer review the measurements and diagnostic evidence after the mission.”

## 12. Return to the automatic dataset demonstration

Open **System Configuration** and click **Open live dataset twin**. This selects `DATASET_ENGINE_010`. The normal local launcher feeds `MISSION_0110` automatically. Watch for **BACKEND CONNECTED**, advancing timestamps, and the actual diagnosed faults.

“Backend telemetry” in this local setup means telemetry delivered by the backend. It is still generated dataset telemetry, not a physical aircraft connection.

## 13. A simple 10-minute running order

| Time | Do this |
|---|---|
| 0:00–0:45 | Aircraft introduction and ENTER |
| 0:45–2:00 | Healthy backend baseline using section 5 |
| 2:00–4:00 | Oil Pressure Drop; pause and explain highlighted oil region |
| 4:00–5:30 | Abnormal Vibration or Misfire |
| 5:30–6:30 | Telemetry chart and diagnostic evidence |
| 6:30–7:15 | Health and RUL explanation |
| 7:15–8:30 | Replay the current recording |
| 8:30–9:15 | Maintenance action and report export |
| 9:15–10:00 | Configuration/adapter boundary and limitations |

Use the extra scenarios in section 7 for questions or a longer presentation. You do not need to click every sidebar page during a short demo.

## 14. If something goes wrong

| Symptom | Action |
|---|---|
| Backend unavailable / demo pauses | Check the launcher terminal is still running; open `http://127.0.0.1:8000/api/v1/health`; restart your own project launcher if needed |
| “No telemetry” | Open System Configuration → Open live dataset twin, or run a simulation first |
| No fault after choosing a scenario | Confirm you clicked **Start demo**, wait for the sample counter, and inspect actual diagnostics; use the checked recipes |
| Sensor warning during “normal” interactive demo | This is a known consequence of constant/missing channels; use section 5 for a baseline |
| Engine looks too zoomed | Click **Reset view** |
| Replay slider disabled | Record a demo or run a backend simulation, then **Open current recording** |
| Report empty or from a different mission | Reports uses the buffered recording; make a new demo recording before exporting |
| Chart stopped but engine values continue | Click **Resume chart**, or pause playback using the top status bar |
| Acknowledge does not remove the highlight | Expected: acknowledgment is not a repair and does not alter backend evidence |
| Imported image does not show precise component highlights | Click **Cutaway** to use the procedural component drawing |

## Rehearsal checklist

- [ ] Launcher and backend health work.
- [ ] I can enter the workspace from the aircraft page.
- [ ] I can show the backend baseline at replay frame 1.
- [ ] I can run Oil Pressure Drop using the exact values above.
- [ ] I can select its simple component highlight and explain its evidence.
- [ ] I can demonstrate a second observed diagnosis.
- [ ] I can replay and export my own recording.
- [ ] I can explain engineering scores, prototype RUL, and categories without reliable UI triggers.

Verification basis: controls and labels were read from the current source; scenario results were checked directly through the same Python twin processor with generated samples. The entire spoken sequence has not been timed in a browser, so rehearse once on your machine before presenting.
