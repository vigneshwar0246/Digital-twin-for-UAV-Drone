# Cooling recall root-cause investigation — 2026-10-10

## Decision

**Release gate: FAIL.** No candidate met the fixed validation decision criteria, so the frozen selection retained the previous research reference. No model was integrated, enabled, merged, or deployed. The existing disabled-by-default ML flag and engineering-rule/statistical fallback are unchanged. These results come from synthetic telemetry and do not establish operational or flight readiness.

The dataset SHA256 (`2b9a25ab4600bebb4d3d1d95504e22889ce86714bb680b7e68d524d3cb68041e`), split manifest, 0.80 per-fault release gate, and audit partitions were unchanged. Challenge and time-forward partitions **had already been inspected before this investigation**. Their descriptive breakdown below is labeled accordingly; they were not used to choose features, weights, model settings, or thresholds. The selected reference and decision rule were saved in `selection.json` before the one-shot audit.

## Reproduction and artifacts

Run from repository root with the scikit-learn 1.7.2 environment. Commands refuse to overwrite frozen selection and audit files; use a new output directory to repeat the series.

```powershell
& 'C:\Users\yogap\anaconda3\python.exe' -B -m backend.model_evaluation.cooling_investigation describe
& 'C:\Users\yogap\anaconda3\python.exe' -B -m backend.model_evaluation.cooling_investigation select
& 'C:\Users\yogap\anaconda3\python.exe' -B -m pytest -q backend/tests/test_experimental_live_features.py
& 'C:\Users\yogap\anaconda3\python.exe' -B -m backend.model_evaluation.cooling_investigation audit
```

`descriptive.json` contains cooling false negatives by engine, mission, severity, and engine × severity for validation and previously inspected audit partitions. `selection.json` contains all candidate configurations, validation metrics, every class's precision/recall, false positives, and full confusion matrices, plus grouped fit checks and the frozen decision. `final_audit.json` contains final per-class metrics and confusion matrices. Tests: **2 passed**, covering offline/streaming parity over 1,668 samples and 49 features, plus missing, invalid, stale, out-of-order, mid-mission, and mission-reset behavior.

## Cooling false negatives and split composition

The frozen reference's validation cooling row has 873 true cooling samples: **7 cooling, 346 Healthy, 253 fuel injector, 245 sensor drift**, and 22 other predictions. Cooling precision is .025 with 278 false-positive cooling alerts.

| Split | Cooling correct / support | Cooling recall / precision | Dominant false negatives | Cooling false positives |
|---|---:|---:|---|---:|
| Validation | 7 / 873 | .008 / .025 | Healthy 346; injector 253; sensor drift 245 | 278 |
| Challenge **previously inspected audit** | 620 / 1,496 | .414 / .794 | Healthy 380; injector 371; sensor drift 54 | 161 |
| Time-forward **previously inspected audit** | 249 / 1,381 | .180 / .412 | Sensor drift 783; Healthy 349 | 355 |

| Split | Cooling mission (engine; generator cylinder) | Support | Recall |
|---|---|---:|---:|
| Fit | 0001 (001; 1), 0006 (006; 2), 0007 (007; 3), 0073 (001; 1) | 377, 469, 519, 360 | Fitting partition |
| Validation | 0057 (009; 1), 0113 (005; 1) | 532, 341 | .009, .006 |
| Challenge **previously inspected audit** | 0011 (011; 3), 0051 (003; 3), 0083 (011; 3), 0094 (010; 2) | 328, 354, 355, 459 | .064, .274, .569, .654 |
| Time-forward **previously inspected audit** | 0085, 0097, 0109 (all engine 001; cylinder 1) | 381, 511, 489 | .273, .284, .000 |

The generator chooses cylinder by `mission_index % 4` and engine by `mission_index % 12`. Both validation cooling missions and every time-forward cooling mission therefore place the largest cooling effect on **cylinder 1**. The generator's sensor-drift fault also affects cylinder 1 only. This is a confirmed coupling in the generator and split composition. It plausibly explains part of the confusion with sensor drift; it does not prove that coupling is the only cause. Challenge's previously inspected cooling missions affect cylinders 2 and 3, where recall is higher but still fails the gate.

By severity, validation cooling recall was **Low .010** (518 samples), **Medium .009** (218), **High .000** (137). The 137 High samples were predicted mostly sensor drift (131). Challenge **previously inspected audit** was Low .297 (1,121) and Medium .765 (375). Time-forward **previously inspected audit** was Low .218 (524), Medium .213 (588), High .037 (269); 259 of the High samples were called sensor drift. Exact prediction counts for every severity, engine, and mission are in `descriptive.json`.

## Physical signature and overlap

The generator applies a gradual, spatially uneven CHT rise with thermal lag. Its forcing depends on load, altitude, ambient temperature, and **airspeed**; it also adds a smaller oil-temperature rise. Baseline CHT depends on airspeed and ambient pressure. The live contract supplies CHT for four cylinders, EGT, load, altitude, ambient temperature, and oil temperature, but **neither airspeed nor ambient pressure**. The experiment used only measurable CHT residual, CHT–EGT gap, peer-cylinder excess, rolling residual, and oil trends. The residual cannot fully remove baseline cooling and weather effects without those unavailable measurements.

There is a population signal but substantial overlap. On validation, median load/ambient/altitude-adjusted CHT residual was **66.6°C** for cooling, **60.5°C** for sensor drift, **61.5°C** for injector, and **46.1°C** for Healthy. Cooling median CHT spread was **10.4°C**, versus **13.3°C** for sensor drift and **9.8°C** for injector. The median cooling oil temperature was **68.8°C**, nearly the sensor-drift median **68.2°C**, reflecting mission/engine operating differences despite the generator's small positive oil effect. Medians alone do not quantify full distribution overlap; the confusion counts above supply direct model-level evidence.

## Controlled fit/validation experiments

All candidates used the same fit and validation partitions, inverse-frequency weights, and sensor-drift ×1.6 cost. Cooling weight was ×5 unless shown. `reference` is the prior selected shallow HGB with 42 live-computable features. New features were added in fixed groups. The bounded estimator checks used shallow, regularized, and baseline HGB plus Extra Trees. GroupKFold over fit **missions** checked reference stability before final audit: cooling recall across three folds was **.000, .101, .000**; fold macro F1 was **.444, .545, .261**. Fold class coverage varies because only four fit cooling missions exist, so this check is descriptive rather than a reliable variance estimate.

| Validation candidate | Cooling recall | Cooling precision | Cooling FP | Macro F1 | Balanced accuracy |
|---|---:|---:|---:|---:|---:|
| Reference, shallow HGB | .008 | .025 | 278 | .656 | .661 |
| + current cooling features | .006 | .019 | 262 | .647 | .658 |
| + current/temporal cooling features | .003 | .011 | 281 | .642 | .653 |
| Same, cooling weight ×10 | .011 | .033 | 294 | .644 | .654 |
| Same, cooling weight ×20 | .055 | .123 | 343 | .645 | .646 |
| Same, regularized HGB | .001 | .003 | 291 | .646 | .652 |
| Same, baseline HGB | .003 | .010 | 294 | .628 | .628 |
| Same, Extra Trees | .005 | .049 | 77 | .570 | .579 |

All other-fault validation recalls, in class order **alternator / bearing / combustion / injector / lubrication / sensor drift / misfire**:

| Candidate | Other-fault recalls |
|---|---|
| Reference | .989 / .647 / .856 / .740 / .320 / .509 / .943 |
| Current cooling | .992 / .698 / .868 / .714 / .219 / .533 / .955 |
| Current + temporal | .987 / .694 / .864 / .721 / .187 / .539 / .953 |
| Weight ×10 | .988 / .706 / .860 / .717 / .188 / .536 / .948 |
| Weight ×20 | .975 / .685 / .773 / .714 / .173 / .555 / .953 |
| Regularized HGB | .986 / .706 / .841 / .720 / .185 / .546 / .947 |
| Baseline HGB | .985 / .691 / .714 / .692 / .178 / .518 / .932 |
| Extra Trees | .895 / .557 / .625 / .625 / .047 / .517 / .962 |

Healthy recall and exact precision/recall for **every** class are in `selection.json`. The ×20 weight had the best cooling recall, yet only .055, with more false positives and material combustion (.856 → .770) and lubrication (.320 → .170) recall losses. It was rejected. The fixed admissibility criteria required validation cooling recall ≥.80, cooling precision ≥.30, macro F1 no more than .03 below reference, and no other fault recall more than .05 below reference. **No candidate qualified.** This is measured evidence that these feature and weight changes do not solve the cooling problem on the frozen validation split.

## Frozen final audit and limits

The frozen selection retained `reference`. The one-shot final audit reproduced validation macro F1 **.656**, challenge **.753**, and time-forward **.612**; cooling recalls **.008**, **.414**, and **.180**, respectively. The original 0.80 per-fault recall gate remains **FAIL** on every required split. Full confusion matrices and all class metrics are in `final_audit.json`.

The generator/cylinder coupling, sparse fit cooling missions, absent live airspeed/pressure, and class-signature overlap are supported concerns. Isolating generator effects would require a **separate versioned dataset investigation** with predeclared label/generator changes and new untouched audit partitions. No labels or synthetic measurements were changed here. The research feature extractor remains separate from production inference; live sampling variation, unavailable sensors, and real fault telemetry still require validation.
