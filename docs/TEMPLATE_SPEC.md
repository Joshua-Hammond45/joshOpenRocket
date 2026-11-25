# Master SolidWorks template spec (v1, basic L1)

Build this once. Members never open it directly: the `Ork2SW` macro Pack-and-Goes it into a fresh folder and pushes the OpenRocket numbers in.

## Rules for the whole template

- Every part and the assembly are **IPS** (inch, pound, second).
- All driving dimensions are **global variables** with the exact names below (case-sensitive). The macro overwrites `"name"= value` in **every document that has that global**, so a part only needs the globals it uses. Derived dimensions are equations on those globals, never typed numbers.
- Values arrive with units (`3.1in`), so equations stay unit-safe.
- Folder: everything flat in one folder (`L1_Rocket.SLDASM` + parts). The macro uses Pack and Go with flatten, so file names stay as you name them here.
- Materials pre-assigned (tube: corrugated paper, rings/fins/bulkhead: pine or plywood, nose: ABS).

## Global variables (from `rocket_params.txt`)

| Name | Unit | Used by | Meaning |
|---|---|---|---|
| `middleBreak` | – | (macro) | 0 = config `SINGLE`, 1 = config `BREAK` |
| `bodyOD`, `bodyID` | in | airframe tubes, rings, nose, bulkhead | airframe diameters |
| `finCanLength` | in | `FinCan_Tube` | aft tube length |
| `upperTubeLength` | in | `BREAK_Upper_Tube` | forward tube, BREAK only |
| `couplerLength`, `couplerOD`, `couplerID` | in | `BREAK_Coupler` | coupler at the break |
| `couplerIntoFinCan` | in | assembly mate | coupler length inside the fin can |
| `bulkheadThickness` | in | `BREAK_Bulkhead` | bulkhead in the coupler |
| `noseLength`, `noseWall`, `noseShoulderLength`, `noseShoulderOD` | in | `Nose_Cone` | tangent ogive |
| `motorTubeOD`, `motorTubeID`, `motorTubeLength` | in | `Motor_Tube`, rings | motor mount |
| `motorTubeAftOverhang` | in | assembly mate | + = motor tube sticks out aft (normally 0) |
| `ringThickness` | in | all rings | 0.25 standard |
| `topRingFromMotorAft` | in | assembly mate | aft face of top ring from motor tube aft end |
| `tNutCount` | – | `Ring_Bottom` | t-nut hole pattern count (2–4) |
| `finCount` | – | `FinCan_Tube` slot pattern, assembly fin pattern | number of fins |
| `finThickness`, `rootChord`, `tipChord`, `sweepLength`, `finSpan` | in | `Fin`, slot width | trapezoid fin (v1 is trapezoid only) |
| `finAftOffset` | in | assembly mate | fin trailing edge from airframe aft end (normally 0) |

## Parts

- **`Motor_Tube`**: two circles `motorTubeOD`/`motorTubeID`, extrude `motorTubeLength`. Origin at aft end.
- **`Ring_Top`**: OD `bodyID`, ID `motorTubeOD`, thickness `ringThickness`. Two 1/4-20 through holes for the U-bolt (hole wizard F/H). U-bolt pre-mated in the assembly.
- **`Ring_Middle`**: same, no holes.
- **`Ring_Bottom`**: same, plus hole-wizard holes for the t-nuts on a circular pattern, count = `tNutCount`. **The t-nut components are pre-mated** (see below).
- **`Fin`**: sketch with `rootChord`, `tipChord`, `sweepLength`, `finSpan`; extrude `finThickness`. Tab: length `= "rootChord" - 0.5`, starting 0.25" from the leading edge, height `= ("bodyID" - "motorTubeOD") / 2` so it always reaches the motor tube.
- **`FinCan_Tube`**: OD/ID `bodyOD`/`bodyID`, extrude `finCanLength`. Fin slot: width `finThickness`, length `= "rootChord" - 0.5`, 0.25" up from the aft end, extrude-cut **up to surface** (outer face), circular pattern count `finCount`.
- **`Nose_Cone`**: tangent ogive revolve (`noseLength`, base dia `bodyOD`), shell `noseWall`, shoulder `noseShoulderOD` × `noseShoulderLength`, rib for the shock cord.
- **`BREAK_Upper_Tube`**, **`BREAK_Coupler`**, **`BREAK_Bulkhead`** (+ its U-bolt/eyebolt): only resolved in config `BREAK`. Name prefix `BREAK_` so they're easy to spot.

## Assembly (`L1_Rocket.SLDASM`)

Mates follow Lecture 2, with distances driven by globals:

1. `Motor_Tube` fixed to the origin (aft end on Top plane), as in the lecture.
2. `Ring_Bottom` concentric, aft face coincident with motor tube aft end, **clocked 45°** to the Front plane so fin tabs never cover the t-nut holes.
3. `Fin` tab tangent to the motor tube, tab aft edge on `Ring_Bottom` forward face; circular component pattern count `finCount`.
4. `Ring_Middle` sits on the fin tabs (coincident), plane-locked against rotation.
5. `Ring_Top` distance mate: aft face `topRingFromMotorAft` from the motor tube aft end.
6. `FinCan_Tube` aft end flush with `Ring_Bottom` aft face (offset `motorTubeAftOverhang`), slots aligned to fins.
7. `Nose_Cone` shoulder fully inside the forward tube (fin can in `SINGLE`, `BREAK_Upper_Tube` in `BREAK`).
8. `BREAK`: coupler concentric, `couplerIntoFinCan` inside the fin can; upper tube butts the fin can; bulkhead inside the coupler.

Configurations: `SINGLE` suppresses every `BREAK_` component and uses the nose mate to the fin can; `BREAK` resolves them and uses the nose mate to the upper tube.

## T-nuts (the reason this template exists)

T-nut components are already inserted and mated in `Ring_Bottom`'s holes, patterned with `tNutCount`, with the **flange on the forward face** (inside the fin can, the face toward the motor's ejection charge). When the motor's ejection charge fires, the casing kicks aft against the retainer, which pulls the t-nut aft; with the flange forward that load seats the flange into the wood instead of pulling the barbs out. Members can't move it because the mate is in the template.

## Checklist before publishing the template

- [ ] Change a few globals by hand (e.g. `bodyOD` 3.1 → 4.0, `finCount` 4 → 3, `rootChord` 6 → 8) and rebuild: no errors, rings and slots follow.
- [ ] Toggle `SINGLE`/`BREAK`: no dangling mates.
- [ ] Run the macro on `tests/data/l1_single.ork` and `l1_break.ork` outputs.
