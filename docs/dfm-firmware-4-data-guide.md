# DFM firmware 4.0.0 recordings: what changed and what pyflic must do with it

For the agent that writes pyflic. DFM firmware 4.0.0 and the matching PyMCU (both on branch `v4_Dev`, October 2026) replace the guessed optogenetic paradigm with explicit, named **Paradigms**, and the recording now carries each Well's Paradigm state in every 200 ms row. This document describes the new wire record, how PyMCU turns it into the data file and the exported `Program.txt`, the firmware rules that produce every new value, and the changes pyflic needs so the new columns drive the analysis instead of being ignored.

Status: the firmware and PyMCU changes pass their PC tests; no bench recording with real DFMs exists yet. Treat the formats below as authoritative for the code, and diff against the first real recording when one arrives (section 11 says which files to compare).

- [1. What changed, in one screen](#1-what-changed-in-one-screen)
- [2. Sources of truth](#2-sources-of-truth)
- [3. Three generations of recording](#3-three-generations-of-recording)
- [4. The recording directory](#4-the-recording-directory)
- [5. The DFM data file, column by column](#5-the-dfm-data-file-column-by-column)
- [6. How the firmware produces the values](#6-how-the-firmware-produces-the-values)
- [7. Program.txt, the 4.0.0 export](#7-programtxt-the-400-export)
- [8. Vocabulary map](#8-vocabulary-map)
- [9. What pyflic must change](#9-what-pyflic-must-change)
- [10. Invariants and pitfalls](#10-invariants-and-pitfalls)
- [11. Reference: wire layouts and golden values](#11-reference-wire-layouts-and-golden-values)

## 1. What changed, in one screen

| Before (firmware 2.0.x / 3.5.0, old PyMCU) | Now (firmware 4.0.0, PyMCU `v4_Dev`) |
|---|---|
| The DFM inferred the paradigm from five numbers (frequency, pulse width, decay, delay, max-time-on) and bits hidden in them | The MCU names a **Paradigm type** (OpenLoop, ClosedLoop, FixedInterval, NonFeeding, ProgressiveRatio, FixedRatio) and its settings explicitly, as a named Paradigm from the Program |
| Progressive ratio counted **milliseconds of contact** ("licks") | Ratio Paradigms count **Events** (feeding bouts separated by an Event gap) |
| Training was N−1 closed-loop activations, signalled by adding 65536 to a Well's signal | **Acclimation** is exactly N closed-loop Activations per Well, reported in a `Phase` column (`A` then `M`) |
| 56-byte status record: signals, LED snapshot, frequency, pulse width, dark | 127-byte record: adds instruction number, Paradigm type, Phase bits, per-Well Activations, Requirement, Progress and LED on-time |
| Data file: 27 columns | Data file: the same 27 columns in the same places, then 63 more: `Interval`, `Cycle`, `Paradigm`, `Phase1-12`, `Activations1-12`, `Requirement1-12`, `Progress1-12`, `OnMs1-12` |
| `W1-W12` could carry +65536 while in training | `W1-W12` are plain 0-1023 signals, always |
| `Program.txt` echoed intervals as `Dark Off,t1..t12,F:,P:,D:,L:,M:,min.` | `Program.txt` has a `Paradigms:` block and interval lines `(stamp) Dark, NAME, t1..t12, N min` with `On`/`Off` thresholds |
| DFM buffer: 1500 records, 60 per reply | 780 records (about 2.6 min of outage), 28 per reply |

pyflic's current reader loads a 4.0.0 file without error, but every Progressive Ratio group reads as "never trained" (no 65536 flag), the `Program.txt` parser rejects every DFM section of the new export, and the sixty-three new columns are unused.

## 2. Sources of truth

Sibling checkouts beside pyflic, both on branch `v4_Dev`. Read these when a detail here is not enough; this document caches what they say as of 2026-10-12.

| What | Where |
|---|---|
| Status record layout (the 127 bytes) | `DFMV3_V2/src/PacketManager.h`, `struct StatusPacket`; a compile-time check pins it at 127 bytes |
| Paradigm rules, Events, Acclimation, Requirement series, OnMs | `DFMV3_V2/src/LEDControl.c` (no hardware calls; runs on a PC) and its tests `DFMV3_V2/tests/test_ledcontrol.c` |
| Record filling, ring buffer, error flags | `DFMV3_V2/src/PacketManager.c`, `src/AnalogInputs.c`, `src/UART2.c` |
| Firmware README: changes per version, error codes, timing, instruction and record tables | `DFMV3_V2/README.md` |
| Record parser and the data-file columns | `PyMCU/StatusPacket.py` (`DATA_COLUMNS`, `PARADIGM_COLUMNS`, `ProcessStatusPacketPletcherV4`, `GetDataBufferPrintPacket`) |
| Instruction numbers, Interval/Cycle lookup, Activation carry past 65535, baselining | `PyMCU/DFM.py` |
| Recording start, file naming, `Program.txt` and `Messages.csv` writing | `PyMCU/DFMGroup.py` |
| Program file format, Paradigm settings and their defaults, the export text | `PyMCU/Paradigm.py`, `PyMCU/Program.py`, `PyMCU/InstructionSet.py`, `PyMCU/Instruction.py`, `PyMCU/docs/ProgramFormat.md` |
| The design and its reasons | `PyMCU/docs/v4-paradigms-plan.md`, `PyMCU/docs/adr/0001-ratio-paradigms-count-events.md`, `PyMCU/docs/adr/0002-status-records-carry-paradigm-state.md` |
| Shared vocabulary (Paradigm, Event, Activation, Requirement, Acclimation, Phase, Linkage) | `PyMCU/CONTEXT.md` |
| Golden bytes both sides test against | `PyMCU/tests/test_protocol.py`, `DFMV3_V2/tests/test_ledcontrol.c` |
| An example Program using every type | `PyMCU/FLICPrograms/ParadigmExamples.txt` |

## 3. Three generations of recording

The file never states the firmware or PyMCU version. Classify each DFM file from its own shape, once, at load, and carry the generation on the loaded DFM so every consumer can branch on it.

| Generation | Written by | Header | Paradigm columns | Training information |
|---|---|---|---|---|
| 1 | old PyMCU, any V3 firmware (2.0.x or 3.5.0) | 27 columns | absent | `W` values above 40000 are in training (value − 65536 is the signal) |
| 2 | PyMCU `v4_Dev`, firmware before 4.0.0 | 90 columns | present, every value empty | **none**: the new PyMCU masks the old training flag out of `W1-W12` and the firmware has no Phase to report |
| 3 | PyMCU `v4_Dev`, firmware 4.0.0 | 90 columns | present and filled | `Phase1-12` |

Detection: `Phase1` absent → generation 1. `Phase1` present and every value empty (pandas reads the blanks as NaN) → generation 2. `Phase1` present with any `A` or `M` → generation 3. `Phase` is filled for every 4.0.0 row, so it is the right column to test; `Paradigm`, `Interval` and `Cycle` can be blank on 4.0.0 rows (section 5.5).

Generation 2 is a real case: a lab with updated MCUs and un-updated DFMs. Its Progressive Ratio recordings have no training end anywhere; say so in `summary.txt` and the report instead of letting `require_training_complete` remove every group silently.

## 4. The recording directory

PyMCU writes one directory per recording, `FLICData/<MCU hostname>_<MM_DD_YYYY_HH_MM>/`, which the experimenter copies to a USB stick. It holds:

| File | Content |
|---|---|
| `DFM<id>_<n>.csv` | One DFM's rows. `n` starts at 0 and a new file starts every 12 hours (`DATA_FILE_SECONDS = 43200`), each with its own header. `Sample` and `Index` continue across files. pyflic's `DFM{id}_*.csv` glob with natural sort already concatenates them. |
| `DFM99_<n>.csv` | The Environmental Monitor (ID 99). **27 columns only**, never the Paradigm columns. Its `W1-W6` are relay and output states (0 or 500). Never load it as a DFM. |
| `Program.txt` | The Program as PyMCU held it when recording started (section 7). Written once, at recording start. |
| `Messages.csv` | `DFM,Date,Time,Millisecond,Sample,Message,MsgType`: "Recording started", "Recording ended", DFM error codes (`DFM code: 02`), "Skipped index", "Repeated index", NACKs, write failures. Useful for integrity reporting; not yet read by pyflic. |

## 5. The DFM data file, column by column

The header is exactly PyMCU's `DATA_COLUMNS + "," + PARADIGM_COLUMNS`:

```
Date,Time,MSec,Sample,W1,W2,W3,W4,W5,W6,W7,W8,W9,W10,W11,W12,Temp,Humid,LUX,VoltsIn,Dark,OptoFreq,OptoPW,OptoCol1,OptoCol2,Error,Index,Interval,Cycle,Paradigm,Phase1,…,Phase12,Activations1,…,Activations12,Requirement1,…,Requirement12,Progress1,…,Progress12,OnMs1,…,OnMs12
```

One row per status record, every 200 ms. An example 4.0.0 row (DFM 1, second Interval of a Program whose A wells have threshold 20 and B wells are `Off`, linkage `1,1,2,2,…`, Well 1 lit for the whole record and Well 2 lit with it by linkage):

```
10/12/2026,20:30:01,400.00,7,112,8,9,7,110,8,8,9,9,8,10,7,23.50,41.20,120.00,3.30,1,40,8,3,0,0,7,2,1,PR10,A,M,A,M,A,M,A,M,A,M,A,M,2,0,1,0,0,0,3,0,1,0,0,0,1,,1,,1,,1,,1,,1,,0,,0,,0,,0,,0,,0,,200,200,0,0,0,0,0,0,0,0,0,0
```

### 5.1 Row time and identity

| Column | Value | Notes |
|---|---|---|
| `Date`, `Time`, `MSec` | `MM/DD/YYYY`, `HH:MM:SS` (24-hour), milliseconds with two decimals | **Derived, not measured**: `recording start + Index × 0.2 s`, where the start is PyMCU's clock when it began recording. Rows sit on an exact 200 ms grid; the DFM's own crystal drift is invisible here. |
| `Sample` | 1, 2, 3, … | PyMCU's count of rows written for this DFM since recording started. Contiguous unless a failed partial write repeated rows. |
| `Index` | 1, 2, 3, … | The DFM's record counter. Restarts at 1 at the buffer reset PyMCU sends when recording starts. A gap means records the DFM lost (its buffer overflowed, see `Error` 0x02); PyMCU drops a record whose Index is not above the last written, so repeats come only from a retried file write. |

### 5.2 Signals

| Column | Value |
|---|---|
| `W1-W12` | Integer 0-1023: the mean of the Well's last 128 ADC scans (about 270 ms) at the record instant. Raw, un-baselined. **The same quantity the firmware compares with the threshold**, sampled every 200 ms. Never offset by 65536. |
| `VoltsIn` | `(mean / 1024) × 3.3 × 2`, two decimals. |
| `Temp`, `Humid`, `LUX` | From the Environmental Monitor read in the same polling round; `0.00` without one. |

Well order is unchanged: `W1` = 1A, `W2` = 1B, `W3` = 2A, … `W12` = 6B, so chamber *c* is wells `2c−1` and `2c`.

### 5.3 Light settings and state

| Column | Value | Notes |
|---|---|---|
| `Dark` | 1 if the DFM's four indicator LEDs were off | On 4.0.0 rows PyMCU fills this from the Program Interval the record's instruction number names, not from the record. 0 when the instruction number is unknown (section 5.5). Dark never affects the OptoLid. |
| `OptoFreq`, `OptoPW` | Hz and ms of the LED pulse train | Same lookup as `Dark`; 0 when unknown. The firmware clamps frequency to 1-500 Hz and pulse width to below one period. |
| `OptoCol1` | 12-bit mask, bit 0 = `W1` | Wells whose pulse train was **active** at the instant the record was made, after linkage. A point sample of a state that changes at 1 ms resolution; `OnMs` is its integral. |
| `OptoCol2` | always 0 | Legacy second column; V3 DFMs never use it. |

### 5.4 Error

The error byte of the record, raw. A bit means the event happened in the roughly 200 ms before the record. Several bits add.

| Bit | Meaning on 3.5.0 and 4.0.0 | pyflic's current label (`integrity_report`) |
|---|---|---|
| 0x01 | A status request arrived before the previous reply was ACKed; the DFM resent those records | "I2C Error" (stale) |
| 0x02 | The DFM's status buffer started to overflow: a record still held was overwritten and is lost | "ID Error" (stale) |
| 0x04 | Unknown command byte | PacketType |
| 0x08 | UART transmit DMA error | DMA_TX |
| 0x10 | UART receive DMA error or receive overrun (the DFM recovers) | DMA_RX |
| 0x20 | Request of the wrong length | PacketSize |
| 0x40 | An ADC scan finished before the previous was processed | AIInterrupt |
| 0x80 | The 1 ms tick fired before the previous was handled | OInterrupt |

On firmware 2.0.0 bit 0x02 meant "not ACKed, resent" and 0x01 was unused; a generation-1 file can come from either, so label bits 0 and 1 together as "No ACK / overflow" there.

### 5.5 Interval, Cycle, Paradigm

Every 4.0.0 record carries the **instruction number** of the instruction the DFM was running. PyMCU numbers each instruction it sends and remembers the last 256, so it can stamp each row with what that instruction was.

| Column | Value | Blank when |
|---|---|---|
| `Interval` | 1-based position of the Interval line within this DFM's `[DFM]` section of the Program | the instruction was not a Program Interval (the idle instruction, or "outputs on"), or the number is unknown |
| `Cycle` | 1-based pass through the Intervals: always 1 for Linear and Constant Programs, counts passes for Repeating, counts days for Circadian | as `Interval` |
| `Paradigm` | The Paradigm's name as written in the Program (`PR10`, `Closed`), or `Idle` for the idle instruction, or a generated name such as `ClosedLoop-40Hz-8ms-Hold500-MaxOn0` for an Interval loaded from an old-format Program | the number is unknown: a record stamped with an instruction this PyMCU session never sent (for example a DFM still running the previous session's instruction) |

Names start with a letter and contain only letters, digits, `_`, `-` and `.`, so the CSV field needs no quoting.

Expect the first few rows of a recording to read `Idle` with blank `Interval` and `Cycle`: PyMCU resets the DFM buffer, starts the file, and sends the first Interval's instruction on its next timer tick. The DFM lights nothing under `Idle`. The columns change on the row after the DFM applied the new instruction, which is the true boundary (within 200 ms), rather than the clock time the Program named.

These three columns make the schedule explicit per row. The Program type rules (Linear holds its last Interval, Repeating wraps, Circadian follows the clock, Constant runs only the first) no longer need reconstructing from `Program.txt` timestamps for generation-3 files.

### 5.6 Phase1-12

`A` while the Well is in **Acclimation**, `M` (Main) otherwise. Rules that decide the value:

- Only FixedInterval, ProgressiveRatio and FixedRatio Paradigms have an Acclimation, and only when the Paradigm sets `Acclimation: N` above 0. Every other Paradigm reports `M` for every Well from its first row.
- A Well whose threshold for the Interval is `On` or `Off` reports `M` always, whatever the Paradigm. A yoked (Off) Well therefore never shows `A`; only Wells with a numeric threshold do.
- A Well leaves `A` when its Nth Acclimation Activation ends (section 6.4), independently of every other Well.
- A new Interval that names a **different** Paradigm resets the Well's state, so `A` can appear again later in the recording. The same Paradigm name across Intervals keeps the state (section 6.7).

### 5.7 Activations1-12

Running count of the Well's own **Activations** since the buffer reset at recording start, as an integer that PyMCU carries past the DFM's 16-bit wrap. Counts Acclimation Activations as well as Main ones. Never reset by an Interval change. Never incremented under OpenLoop, or for a Well set `On` or `Off`, or by light the Well receives through Linkage (section 6.3 says what one Activation is per type).

The increments are exact event markers: a row whose `Activations_w` is one above the previous row's holds the start of one Activation at Well *w* somewhere in its 200 ms. Two increments in one row are possible only when an Activation can be shorter than 200 ms.

### 5.8 Requirement1-12 and Progress1-12

Filled only when the Paradigm is ProgressiveRatio or FixedRatio **and** the Well has a numeric threshold. Blank otherwise (non-ratio Paradigms, `On`/`Off` Wells, `Idle`).

- `Requirement`: Events the Well needs for its next Activation. Under FixedRatio it is the `Ratio`. Under ProgressiveRatio it is the series value for the next Main-phase Activation (section 6.5). During Acclimation it already shows the first Main Requirement.
- `Progress`: Events counted toward that Requirement so far. Returns to 0 when the Activation starts. Stays 0 throughout Acclimation.

A `Progress` increment is a firmware-detected **Event** at that Well, so firmware Events are observable directly for ratio Paradigms: total Events since the Paradigm state began = Σ(Requirements met) + current `Progress`.

### 5.9 OnMs1-12

Milliseconds within the record's 200 ms during which the Well's LED pulse train was active, **after Linkage**: a yoked Well's `OnMs` mirrors its partner's light. Normal range 0-200; the counter saturates at 255 and only exceeds 200 when a record was late. "Active" means the pulse train was running; physical LED-on time within it is `OnMs × PulseWidth × Frequency / 1000`.

`Σ OnMs / 1000` is the exact light-on seconds for a Well. `OptoCol1` sampled at 5 Hz is only an estimate, and misses Activations shorter than 200 ms entirely when they fall between samples.

### 5.10 Blank rules, summarised

| Columns | Generation 2 | Generation 3 |
|---|---|---|
| `Interval`, `Cycle` | blank | blank for `Idle`/unknown instructions |
| `Paradigm` | blank | blank for unknown instructions; `Idle` before the first Interval |
| `Phase*`, `Activations*`, `OnMs*` | blank | always filled |
| `Requirement*`, `Progress*` | blank | filled for ratio Paradigms on numeric-threshold Wells only |
| `Dark`, `OptoFreq`, `OptoPW` | from the record (old firmware reports them) | from the instruction lookup; 0 when unknown |

pandas reads the blank numeric columns as float with NaN. Cast `Activations*` and `OnMs*` to int only on generation 3; keep `Requirement*`/`Progress*` nullable.

## 6. How the firmware produces the values

Everything below runs in `LEDControl.c`, once per millisecond, per Well, with no knowledge of chambers, pairing or yoking. Those are pyflic's concepts, built from Linkage and thresholds.

### 6.1 Signal and contact

- The ADC scans all 12 Wells about 477 times a second (one scan every ~2.1 ms). Each Well's **signal** is the mean of its last 128 scans, about 270 ms of smoothing. `W1-W12` are this signal sampled every 200 ms.
- The MCU sends each Well a **threshold** in the same 0-1023 units. With `Baseline: Yes` (the default), PyMCU adds the Well's baseline to the authored threshold before sending: the baseline is the mean of that Well's signal over 10 consecutive status records (about 2 s) read after the Program was staged and **before recording started**, so the baseline window is not in the data file. With `Baseline: No` the authored value is sent as is.
- A Well is in **contact** while signal > threshold, evaluated every 1 ms.
- Threshold `On` (wire value 0xFFFE) lights the Well's LED constantly and `Off` (0xFFFF) never lights it by its own Paradigm. Both bypass the Paradigm entirely, so such Wells report no Phase, Activations, Requirement or Progress of their own.

### 6.2 Events and the Event gap

An **Event** is one feeding bout as the firmware sees it:

- It starts when contact begins **and no Activation of this Well's own Paradigm is in progress**. Contact that begins while the Well is lit by its own Paradigm starts no Event; light from a linked Well does not matter.
- It ends once the signal has stayed below the threshold for `EventGapMs` continuously (default 100 ms). A dip shorter than the gap is still the same Event.

Ratio Paradigms and Acclimation count Events. pyflic's own feeding events (dual-threshold licks linked across `feeding_event_link_gap`) are a different detector on the same signal; expect them to agree in the main and disagree at the edges.

### 6.3 Activations, by Paradigm type

An **Activation** is one LED on-period that a Well's own Paradigm starts. All times are milliseconds; the settings are the Paradigm's.

| Type | Light rule | One Activation | Counted in `Activations` |
|---|---|---|---|
| OpenLoop | Lit for the whole Interval, except `Off` Wells. Other thresholds are ignored. | none | never |
| ClosedLoop | Lit during contact and for `HoldMs` after it ends. A continuous on-period is cut off after `MaxOnMs` (0 = no limit); the LED then stays dark until the current Event ends, and the next Event can light it again. | from the LED coming on to the hold running out or the cut-off | each time the LED comes on |
| FixedInterval | Contact starts an Activation of exactly `ActivationMs`. No new one can start until `LockoutMs` after the previous one **started**; once the lockout has passed, contact already in progress starts the next. | exactly `ActivationMs` | each start |
| NonFeeding | Lit when the Paradigm starts. Off during contact. Comes on `OnDelayMs` after contact ends, for at most `MaxOnMs` (0 = no limit). | each on-period | each time the LED comes on |
| ProgressiveRatio | The Event that brings `Progress` up to `Requirement` starts an Activation of exactly `ActivationMs`; `Progress` returns to 0 and `Requirement` moves along the series. | exactly `ActivationMs` | each start |
| FixedRatio | As ProgressiveRatio with a constant Requirement of `Ratio`: the first Activation comes at Event number `Ratio`. | exactly `ActivationMs` | each start |

Under every type, a rise during the Well's own Activation starts no Event, so the fly cannot chain Activations by holding contact: the next Event needs a gap of `EventGapMs` first.

### 6.4 Acclimation and Phase

`Acclimation: N` on a FixedInterval, ProgressiveRatio or FixedRatio Paradigm gives each Well N closed-loop Activations before its main rule starts:

- While in Phase `A`, each Event lights the LED during contact and for `ActivationMs` after it (closed loop with `ActivationMs` as the hold).
- Each such Event counts one Acclimation Activation, in `Activations`.
- When the Nth Acclimation Activation **ends** (the LED goes off), the Well moves to Phase `M`. It gets exactly N Activations; the old firmware gave N−1.
- The ratio series starts afresh in `M`: the first Main Activation needs `Requirement` for k = 1. `Progress` stays 0 throughout `A`.
- Counted per Well, so Wells of one DFM leave Acclimation at different times.

This is what pyflic calls **Training**. Its end is now a column value, not an inference from a signal offset.

### 6.5 Requirement series

k counts **Main-phase** Activations since the Paradigm state began (k = 1 for the first). Acclimation Activations do not advance k.

- Arithmetic: `Requirement_k = FirstRequirement + Step × (k − 1)`, capped at `Cap`. Defaults: FirstRequirement 1, Cap 65535. Example `Step: 10, Cap: 200` → 1, 11, 21, … 191, 200, 200, …
- Exponential (Richardson-Roberts): `Requirement_k = round(Scale × e^(Rate × k) − Scale)`, capped. Defaults Scale 5, Rate 0.2 → 1, 2, 4, 6, 9, 12, 15, 20, 25, 32, 40, 50, 62, 77, 95, … (the firmware test pins these fifteen values).
- FixedRatio: `Requirement_k = Ratio`.
- Always at least 1 and at most 65535.

The `Requirement` column is the firmware's own number, so pyflic reads the ratio met instead of estimating it; `Program.txt` carries the series settings for cross-checking.

### 6.6 Per-Well On/Off and Linkage

- Thresholds are per Well per Interval. `On` and `Off` override the Paradigm for that Well (section 6.1).
- **Linkage** (`Linkage: 1,1,2,2,…`) groups Wells; every LED in a group is lit whenever any Well in the group is lit. It is sent as a separate message and applies for the whole recording. Each Well still runs its own Paradigm: in a linked FixedRatio pair, each Well counts its own Events. `OptoCol1` and `OnMs` are after Linkage; `Activations`, `Requirement`, `Progress` and `Phase` are the Well's own.
- The typical choice assay: `Linkage: 1,1,2,2,3,3,4,4,5,5,6,6`, A wells with a numeric threshold, B wells `Off`. Only the A well triggers, both LEDs of the chamber light. A yoked chamber is a chamber whose wells are `Off` and linked to a treatment chamber's trigger well.

### 6.7 State across Intervals, resets, and the Idle Paradigm

- **Keep-state.** When the next Interval names the same Paradigm as the last instruction PyMCU sent, PyMCU sets the instruction's keep-state flag and the DFM keeps every Well's Phase, Requirement, Progress and timers. Threshold-only and Dark-only changes, and Repeating wraps, keep state this way. A different Paradigm name resets every Well's state (Phase back to `A` if the new Paradigm has Acclimation).
- **Activations never reset mid-recording**, whatever the Paradigm does. They reset only with the buffer reset.
- **Buffer reset (recording start).** PyMCU sends it once when recording starts; the DFM clears its record buffer, restarts `Index` at 1, resets every Well's Paradigm state and zeroes `Activations`. PyMCU zeroes its carried totals at the same time.
- **Idle.** From power-up until its first instruction, and whenever PyMCU sends the idle instruction (program stopped, "outputs off"), the DFM runs a ClosedLoop Paradigm with every Well `Off`: nothing lights, `Paradigm` reads `Idle`.
- **Instruction numbers** start at a random value per PyMCU session and increment with every instruction sent, so a stale number from a previous session is unlikely to collide; when it does not match, the row's `Interval`, `Cycle` and `Paradigm` are blank and `Dark`, `OptoFreq`, `OptoPW` are 0.

### 6.8 Timing

- Paradigm logic and LED mask: every 1 ms (TMR2).
- Status record: every 200 ms (TMR1). `OnMs` is the count of 1 ms steps since the previous record; the LED snapshot, Phase, counts and signals are taken at the record instant.
- ADC: ~477 scans/s; the 128-scan mean lags a step change by up to ~270 ms, which the firmware and the data see identically.
- Reply path: the DFM buffers 780 records (~2.6 min); PyMCU polls every ~0.3 s and drains backlogs with extra reads. Longer outages lose the oldest records and raise `Error` 0x02.

## 7. Program.txt, the 4.0.0 export

PyMCU writes `str(currentProgram)` once at recording start. Whatever format the experimenter authored (new named-Paradigm lines or old 14/19-number lines), **the export is always in the new format**; old lines appear as generated Paradigm names.

### 7.1 Example

Generated by PyMCU `v4_Dev`'s own export code (`str(MCUProgram)`) from a Program with two named Paradigms, one DFM section in the new form (DFM 1), one in the old 19-number form (DFM 3), a connected DFM with no section (DFM 2) and an `[ENVMON]` section:

```
Start Time: 10/12/2026 20:00:00
End Time: 10/13/2026 02:00:00
Duration: 360 min
Default Linkage: 1,1,2,2,3,3,4,4,5,5,6,6
Default Program Type: Linear
Baseline: Yes

Paradigms:
Closed (ClosedLoop): Frequency 40 Hz, PulseWidth 8 ms, HoldMs 500 ms, MaxOnMs 0 ms, EventGapMs 100 ms
PR10 (ProgressiveRatio): Frequency 40 Hz, PulseWidth 8 ms, ActivationMs 500 ms, Series Arithmetic, FirstRequirement 1, Step 10, Cap 200, EventGapMs 100 ms, Acclimation 10
ClosedLoop-40Hz-8ms-Hold500-MaxOn0 (ClosedLoop): Frequency 40 Hz, PulseWidth 8 ms, HoldMs 500 ms, MaxOnMs 0 ms, EventGapMs 100 ms
Idle (ClosedLoop): Frequency 40 Hz, PulseWidth 8 ms, HoldMs 0 ms, MaxOnMs 0 ms, EventGapMs 100 ms

***DFM 1***
Linkage: 1,1,2,2,3,3,4,4,5,5,6,6
Program Type: Linear
(10/12/2026 20:00:00) Dark, Closed, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 30 min
(10/12/2026 20:30:00) Dark, PR10, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 330 min

***DFM 2***
Linkage: 1,1,2,2,3,3,4,4,5,5,6,6
Program Type: Linear
(10/12/2026 20:00:00) Lit, Idle, Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off, 360 min

***DFM 3***
Linkage: 1,1,2,2,3,3,4,4,5,5,6,6
Program Type: Linear
(10/12/2026 20:00:00) Lit, ClosedLoop-40Hz-8ms-Hold500-MaxOn0, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 360 min

***Env Mon***
Linkage: 1,1,2,2,3,3,4,4,5,5,6,6
Program Type: Linear
(10/12/2026 20:00:00) Lit, Idle, 1,On,1,1,On,On,On,On,On,On,On,On, 120 min
(10/12/2026 22:00:00) Dark, Idle, On,On,On,On,1,1,On,On,On,On,On,On, 120 min
```

Points the example shows:

- `Idle` and generated names appear in the `Paradigms:` block like any other Paradigm.
- DFM 2 was connected but had no `[DFM]` section: PyMCU gives it one Interval, `Idle`, all `Off`, with the global Linkage.
- DFM 3's old-form line (`0,20,-1,…,40,8,500,0,0,360`) became a ClosedLoop Paradigm named from its settings, with `-1` printed as `Off`.
- The Env Mon's relay and output states are printed through the threshold formatter, so a `0` state prints as `On` and a `1` as `1`. Ignore the section; the Environmental Monitor's own data file is unchanged.

### 7.2 Grammar

- **Header** (before any `***` section): `Start Time`, `End Time` (`MM/DD/YYYY HH:MM:SS`), `Duration: N min` (`{:g}` formatting, so `360 min` or `30.5 min`), `Default Linkage`, `Default Program Type`, `Baseline: Yes|No`. The old `Default Opto Frequency/Pulsewidth/Delay/Decay/Max Time On` lines are gone.
- **`Paradigms:`** then one line per Paradigm used by any DFM: `NAME (Type): Setting value[ unit], …`. Settings appear in a fixed order per type, every setting the type has (defaults included), with units ` Hz` on Frequency, ` ms` on PulseWidth, `*Ms` settings and EventGapMs, none on counts, `Series Arithmetic|Exponential`, and decimals (`Scale 5`, `Rate 0.2`) in `{:g}` form. Only the settings of the chosen Series are printed for ProgressiveRatio. The lines carry commas, which is why they must be matched before the interval-line parser sees them.
- **Sections** `***DFM n***` and `***Env Mon***`, each with `Linkage:` and `Program Type:` lines, then interval lines. Env Mon intervals use the same shape with relay/output states in the threshold slots; ignore the section.
- **Interval line**: `(MM/DD/YYYY HH:MM:SS) Dark|Lit, NAME, t1,t2,…,t12, N min`. The stamp is the first-pass start (`StartTime + elapsed start`). Thresholds are an integer 1-1023, `On` or `Off`. Only Intervals whose first-pass start falls inside the Duration are printed.
- Values are case-insensitive in the loader; the export writes them as above.

Thresholds printed are the ones PyMCU held when recording started: on the first run of a loaded Program these are the authored values, and the DFM compares the signal with `threshold + baseline` under `Baseline: Yes`. A Program run a second time without being reloaded prints the previous run's baseline-adjusted values instead (PyMCU adds the baseline into the shared instruction objects after the export is written), so a threshold far above the authored value is that case, not a different Program.

A recording started without a Program file (plain "record for N minutes") exports an `***ALL DFM***` block instead of DFM sections. Treat it as "no program": every Well `Off`.

### 7.3 Why pyflic's current parser rejects the export

`pyflic/base/opto_program.py` was written for the pre-4 export. On the new one:

| Line | What the parser does |
|---|---|
| `Paradigms:` and each `NAME (Type): …` line | unknown header key → skipped with a warning (harmless) |
| `(stamp) Dark, PR10, 20,Off,…, 330 min` | head token `Dark` fails `_DARK_RE` (it expects `Dark Off`/`Dark On`) and `int("Dark")` fails → `ValueError` → the whole DFM section is **dropped** |
| every section dropped | `ProgramError("no DFM section could be read …")` → `opto_program_error` set, the light QC runs as if there were no program, and the Progressive Ratio type cannot derive `paired_chambers` |

Verified on the example above with the current `parse_program`:

```
ProgramError: Program.txt: no DFM section could be read (DFM 1: interval 1 (line 16): dark-running field 'Dark' not understood; DFM 2: interval 1 (line 22): dark-running field 'Lit' not understood)
```

Even with the dark field accepted, `PR10` is not an integer threshold, `Off`/`On` are not integers, there are no `F:`/`P:`/`D:`/`L:`/`M:` keys, and `330 min` is parsed as the duration only because the plain-token path takes the last token. The parser needs a second grammar, not a patch.

### 7.4 Joining Program.txt to the rows

- Row `Paradigm` = the `NAME` in the `Paradigms:` block → the type and settings (decay-like quantities, Acclimation N, series).
- Row `Interval` = the 1-based position of the interval line in that DFM's section → the thresholds per Well for that row (trigger wells, `On`, `Off`) and `Dark`.
- Row `Cycle` with `Program Type` → which pass; only needed for reporting.
- `Linkage:` of the section → linkage groups, unchanged for the recording.

For generation-1 files keep the existing clock-time schedule reconstruction; for generation 3 the rows are the schedule.

## 8. Vocabulary map

pyflic's `CONTEXT.md` and PyMCU's `CONTEXT.md` fix different words for overlapping things. Translate at the data boundary; keep each codebase's own words inside it.

| pyflic | Firmware / PyMCU | Relationship |
|---|---|---|
| Training (Progressive Ratio) | Acclimation, Phase `A` | The same phase. pyflic's glossary lists "acclimation" under *Avoid*; the firmware now defines it precisely as N closed-loop Activations per Well. Keep "Training" in pyflic prose, and say in the glossary that the data column calls it Acclimation. |
| training end | first row where the Well's Phase reads `M` after `A` | Now a column transition, per Well |
| Light Event (one onset of a group's light) | Activation (one on-period of a **Well's own** Paradigm) | A group's Light Event is the Activation of its trigger Well. A yoked Well has light but no Activations. |
| lick (a baselined sample above threshold) | contact (signal above threshold, per 1 ms) | Different detectors on the same signal |
| feeding event (licks linked across the link gap) | Event (contact bouts separated by `EventGapMs`) | Different detectors; the firmware's is visible as `Progress` increments under ratio Paradigms |
| requirement (licks per light period, estimated) | Requirement (Events per Activation, recorded) | Recorded in the data now |
| decay | `HoldMs` (ClosedLoop) or `ActivationMs` (FixedInterval, ratio types, Acclimation) | PyMCU retired "decay" |
| delay | `LockoutMs` (FixedInterval) or `OnDelayMs` (NonFeeding) | |
| max time on | `MaxOnMs` | |
| open loop / closed loop / fixed interval / progressive ratio / non-feeding activation | OpenLoop / ClosedLoop / FixedInterval / ProgressiveRatio / NonFeeding, plus **FixedRatio** (new) | One new type |
| Opto Program | Program (the export) | |
| Linkage Group | Linkage | |
| Trigger Well | a Well with a numeric threshold | `On` = open loop for that Well; `Off` = never triggers |
| Paired / Yoked chamber | no firmware concept | Paired = the chamber holding the trigger Well; Yoked = the `Off` chamber linked to it |
| Facet, time window, bin | — | pyflic-only |
| `Interval` column of `binned_feeding_summary` (`(a,b]` labels) | `Interval` column of the data file (Program step) | **Name clash** in two different tables; never merge them by column name |
| Status record / row | Status record (never "packet", which is the transport unit) | |

## 9. What pyflic must change

Each item names the module, what to do, and the condition that says it is done. Do them in order; later items read what earlier ones expose.

### 9.1 Load and classify the generation (`pyflic/base/dfm.py`)

Add the generation to `_LoadedDFM` and `DFM` (section 3's rule, on `Phase1`). Expose it on the loaded `DFM` and name it in `summary.txt` and the integrity report. Keep `version` (2 or 3, from the filename) as it is; generation is a second axis.

Done when: a 27-column file, a 90-column file with empty Paradigm columns, and a filled 90-column file each load, each reports its generation, and `with_params` carries it unchanged.

### 9.2 Training end from Phase (`dfm.py`, `progressive_ratio_experiment.py`)

Replace the 65536 flag as the source of training on generation 3:

- Per Well, training end = `Minutes` of the first row whose `Phase_w` is `M` after at least one `A` row. A Well with no `A` row has no training (Acclimation 0, or not a trigger Well); that is not a QC note for a non-trigger Well.
- Keep `_calculate_progressive_ratio_training` for generation 1 unchanged. On generation 2 set every Well to `never_flagged` and add the summary line "no training information: recorded with DFM firmware older than 4.0.0" (section 3).
- The group's training end is still the Paired Sucrose Well's. The other three Wells of a Chamber Group now read `M` from the start (they are `Off`), so retire the "stayed flagged to the end" and "cleared at a different minute" notes on generation 3; a second `A` run on the same Well later in the recording is a note ("Paradigm restarted at Interval k").
- Cross-check: during the `A` run, `Activations_w` must rise by exactly the Paradigm's `Acclimation` N. A mismatch is a QC warning naming both numbers.

Done when: on a generation-3 fixture with `Acclimation: 3`, `training_table()` gives each group the minute its Paired Sucrose Well first reads `M`, `TrainingComplete` is true only for groups that reached `M`, and the generation-1 fixtures in `tests/pr_fixtures.py` still pass unchanged.

### 9.3 Light state from `OptoCol1` and `OnMs` (`dfm.py`)

- Keep `lights_df` (per-sample booleans from `OptoCol1`) as the common denominator across generations.
- Add a per-Well on-time frame from `OnMs1-12` on generation 3. `OptoOn_sec`, `OptoOn_sec_A/B` and `LightOn_sec` use `Σ OnMs / 1000` when it exists, else the sampled estimate; the summary says which.
- Light-event onsets for a trigger Well on generation 3 come from `Activations_w` increments (section 5.7); `OptoCol1` onsets remain the fallback and the only source for linked-only Wells.

Done when: a fixture with 300 ms Activations every 2 s gives the exact on-time from `OnMs` and the exact onset count from `Activations`, while `OptoCol1` alone undercounts, and the discrepancy is reported, not hidden.

### 9.4 Parse the 4.0.0 export (`pyflic/base/opto_program.py`)

Add a second grammar beside the existing one and choose by content: a `Paradigms:` line, or an interval line whose head token is bare `Dark`/`Lit`, means the new export.

- Parse the `Paradigms:` block into a `Paradigm` object: name, type (the six), settings as given (defaults appear explicitly in the export). Match these lines **before** the interval-line parser, since they contain commas.
- Parse interval lines `(stamp) Dark|Lit, NAME, t1..t12, N min`: thresholds as int, `On` (open loop for that Well) or `Off` (never triggers); the Paradigm by name.
- Present the same `DFMProgram`/`ProgramInterval` API to the QC, and give `ProgramInterval` a `paradigm` (new export) beside `params` (old export). Derive the quantities the QC already asks for from the Paradigm: `decay_ms` = `HoldMs` for ClosedLoop, `ActivationMs` for FixedInterval and ratio types (and for Acclimation rows), none for NonFeeding and OpenLoop; `paradigm` mode names, with FixedRatio added to the feeding paradigms.
- `program_rows()` / `opto_program.csv` show type and settings instead of decoded `F`/`P`.
- Ignore `***Env Mon***` and `***ALL DFM***` sections; keep the old-export path for generation-1 recordings.

Done when: `tests/test_opto_program.py` parses the example in section 7.1 (and a generated name such as `ClosedLoop-40Hz-8ms-Hold500-MaxOn0`) with every DFM section accepted, `trigger_wells()` returns the numeric-threshold Wells, `open_wells()` the `On` Wells, and the old-format fixtures still parse unchanged.

### 9.5 Judge light under explicit Paradigms (`pyflic/base/opto_qc.py`, `opto_light.py`)

- On generation 3, window rows by runs of (`Interval`, `Cycle`) from the data; join the Paradigm and thresholds from `Program.txt` by name and Interval index (section 7.4). Use the clock-time schedule only for generation 1 and for rows whose `Interval` is blank (report those separately: `Idle` at the start is normal; unknown instructions are a finding).
- Mode per Linkage Group per window: any member `On` → open loop; every member `Off` → off; OpenLoop type → open loop for its non-`Off` members; else the Paradigm type. Rows in Phase `A` on a Well are closed loop with hold `ActivationMs` for that Well, whatever the Paradigm.
- Explained Light per type: ClosedLoop as today with `HoldMs` as the decay and `MaxOnMs` as the cut-off; FixedInterval: light is one `ActivationMs` block per Activation and contact during `LockoutMs` without light is expected; ratio types: light only at the Event that met the Requirement, so most contact is rightly unlit; NonFeeding: light is the complement of contact, not judged.
- Prefer the firmware's own decisions where recorded: `Activations_w` increments mark exactly when the Well's Paradigm lit; a `Progress_w` increment with no pyflic lick or touch at Well *w* is the "the sensor saw contact pyflic did not" signature directly, without emulating the trigger.
- Emulated Trigger on generation 3: contact ≈ `W_w > threshold + baseline`; the baseline window is not in the file (section 6.1), so take the first 10 rows (the `Idle` lead-in, LEDs off) and mark the emulation approximate.
- The program-versus-data checks on `OptoFreq`, `OptoPW` and `Dark` still work (PyMCU fills them from the same instruction); add a check that the row's `Paradigm` name exists in `Program.txt`.

Done when: a generation-3 fixture of each type passes with no unexplained light; a fixture whose `Activations` rise with no lick at the trigger Well flags that group; `opto_program.csv` and `opto_light_intervals.csv` name the Paradigm type and its settings.

### 9.6 Progressive Ratio on recorded Requirement and Progress (`progressive_ratio_experiment.py`, `pr_light_qc.py`, `pr_breaking_point.py`)

- Light Events of the Paired chamber on generation 3 = `Activations` increments of its Sucrose Well, onset at the row time (≤ 200 ms late). The `OptoCol1`-based detection stays for generation 1.
- Add to the Light Event Ledger: `Requirement` (the ratio that Activation met, read from the row before the increment), `FirmwareEvents` (Events the firmware counted since the previous Activation = that Requirement), and the Phase.
- `LargestRequirement` becomes the recorded Requirement; report the Breaking Point as both the count of lick-backed Test Activations and the last Requirement met. ADR-0014's "the firmware's lick schedule is not recorded" no longer holds; note it in the ADR's addendum.
- Light QC: the lick-free rule stays (pyflic licks versus firmware Activations). Add the firmware's own Event count beside pyflic's licks per Light Event so "no increasing trend" can be judged on the Requirement series itself.
- Yoked chamber: `Activations` of both its Wells stay 0; `OnMs` mirrors the Paired light. Use that to verify yoking rather than assuming it.
- `paired_chambers` from the program: the trigger-well derivation works unchanged once 9.4 lands.

Done when: on a generation-3 PR fixture the ledger's `Requirement` column matches the arithmetic series the Program states, `pr_breaking_point.csv` gains the last-Requirement column, and verdicts on `test_data/progressive_ratio` (generation 1) are unchanged.

### 9.7 Integrity report (`dfm.py`)

- Error bit labels per section 5.4, by generation.
- `Index` starts at 1 and increments by 1; report gaps as lost records with their time, and repeats as rewritten rows; `Sample` contiguous.
- Count rows with blank `Paradigm` (unknown instruction) and rows with `OnMs > 200` (late records); list the distinct `Paradigm` names with their row counts and first/last minute.
- Read `Messages.csv` when present and list its ERROR rows.

Done when: the report names the generation, the lost-record count, and the Paradigm sequence for a generation-3 file, and is unchanged for generation 1.

### 9.8 Fixtures and tests (`tests/`)

- Add `write_v4_csv` beside `pr_fixtures.write_pr_csv` and `opto_fixtures.write_opto_csv`: the 90-column header, `Phase`/`Activations`/`Requirement`/`Progress`/`OnMs` derived from the fixture's own simulated feeding under section 6's rules (a few dozen lines of per-ms simulation is enough), `Interval`/`Cycle`/`Paradigm` per row, and `OptoCol1` as the mask at each 200 ms instant.
- Add a `write_v4_program` writer producing section 7's text, sharing the thresholds and Paradigm settings with the CSV builder.
- Golden values to assert against: the exponential series in section 6.5; Acclimation giving exactly N; `Requirement` blank on `Off` Wells; `Activations` 0 on yoked Wells; `OnMs` equal on both Wells of a linked pair.
- A generation-2 fixture (90 columns, Paradigm columns empty) for the refusal path in 9.2.

Done when: every new behaviour above has a test on a generation-3 fixture and `uv run pytest tests/` passes with the existing generation-1 tests untouched.

### 9.9 Help topics and the glossary

- `pyflic/help/content/concepts-progressive-ratio.md`, "Training": the flag description becomes the `Phase` column for 4.0.0 recordings, with the 65536 rule kept for older files.
- `pyflic/help/content/concepts-optogenetics.md`, "Program.txt": the new interval line and the `Paradigms:` block; the six types and which settings play the decay role.
- `CONTEXT.md`: under *Training* add that the data column calls it Acclimation (Phase `A`) from firmware 4.0.0; under *Light Event* add that for 4.0.0 data it is read from the trigger Well's `Activations`; add **Generation** as a term. Record the decision as an ADR (`docs/adr/0016-…`).
- `uv run pytest tests/test_help_refs.py` still passes.

## 10. Invariants and pitfalls

- `W1-W12` are the firmware's own signal (128-scan mean) at 5 Hz. Re-deriving contact from them reproduces the firmware's test up to timing between samples; the baseline it added is not in the file.
- `Phase` `M` on a Well means "not in Acclimation", which for an `Off` or `On` Well, or under a Paradigm without Acclimation, says nothing about training.
- `Activations` includes Acclimation Activations. The series index k in `Requirement` counts Main-phase Activations only.
- `Activations` never increments under OpenLoop, for `On`/`Off` Wells, or for light received through Linkage. `OnMs` and `OptoCol1` include linked light. A yoked Well shows light with zero Activations.
- `Requirement`/`Progress` blank = not a ratio Paradigm or not a numeric-threshold Well. `Requirement` ≥ 1 wherever filled. `Progress` stays 0 during Phase `A`.
- `OnMs` is pulse-train-active time, 0-200 normally, 255 at saturation; multiply by the duty cycle for LED-on time.
- `OptoCol1` is a point sample; Activations shorter than 200 ms can be missing from it entirely while `OnMs` and `Activations` show them.
- `Dark`, `OptoFreq`, `OptoPW`, `Interval`, `Cycle`, `Paradigm` on 4.0.0 rows come from PyMCU's instruction lookup, not from the record. Unknown instruction → blanks and zeros. `Idle` rows open every recording.
- `Date`/`Time`/`MSec` are `start + Index × 0.2 s`; the recording origin is PyMCU's clock at recording start; rows are an exact 200 ms grid.
- `Index` restarts at 1 per recording and continues across the 12-hour file splits; a gap is lost records (`Error` 0x02 marks the start of the overflow); a repeat is a rewritten batch after a failed write, so de-duplicate by `Index`.
- Same Paradigm name across consecutive Intervals keeps Phase, Requirement and Progress; a different name resets them. Activations persist across all Intervals.
- Event gap default 100 ms; ratio Paradigms count Events, where firmware 2.x counted milliseconds of contact (one second of contact was 1000 "licks").
- FixedRatio is a new type with no pre-4 equivalent.
- `DFM99_*.csv` is the Environmental Monitor with 27 columns; `Program.txt`'s `***Env Mon***` section is not a DFM.
- pyflic's binned tables already have a column named `Interval`; the data file's `Interval` is a Program step.
- Generation 2 files have no training information at all; say so rather than removing every group.

## 11. Reference: wire layouts and golden values

For fixture building and for diffing against the first bench recording. pyflic never sees these bytes; PyMCU's `StatusPacket.py` and the firmware's `PacketManager.h` must agree on them, and `PyMCU/tests/test_protocol.py` plus `DFMV3_V2/tests/test_ledcontrol.c` check the same golden bytes on both sides.

### 11.1 Status record, 127 bytes, big-endian

| Offset | Field | Bytes | Data-file column |
|---|---|---|---|
| 0 | DFM ID | 1 | (file name) |
| 1 | Error flags | 1 | `Error` |
| 2 | Instruction number | 2 | → `Interval`, `Cycle`, `Paradigm`, `Dark`, `OptoFreq`, `OptoPW` via PyMCU's lookup |
| 4 | Paradigm type 0-5 | 1 | → whether `Requirement`/`Progress` are written |
| 5 | Phase bits, bit 0 = Well 1, 1 = Acclimation | 2 | `Phase1-12` |
| 7 | Well signals, mean of last 128 scans | 12 × 2 | `W1-W12` |
| 31 | VoltsIn | 2 | `VoltsIn` |
| 33 | LED state after Linkage, bit 0 = Well 1 | 2 | `OptoCol1` |
| 35 | On-time per Well since the last record, ms, saturating at 255 | 12 × 1 | `OnMs1-12` |
| 47 | Activations per Well since the buffer reset, wraps at 65536 | 12 × 2 | `Activations1-12` (carried past the wrap by PyMCU) |
| 71 | Requirement per Well, 0 unless a ratio type on a numeric-threshold Well | 12 × 2 | `Requirement1-12` |
| 95 | Progress per Well, as above | 12 × 2 | `Progress1-12` |
| 119 | Record index | 4 | `Index` |
| 123 | Checksum: two's complement of the byte sum of bytes 0-122 | 4 | — |

Paradigm type codes: 0 OpenLoop, 1 ClosedLoop, 2 FixedInterval, 3 NonFeeding, 4 ProgressiveRatio, 5 FixedRatio.

### 11.2 Paradigm instruction (command 0xF7), 63 bytes after COBS decoding

| Offset | Field | Bytes |
|---|---|---|
| 0 | ID, 0xF7 | 1 + 1 |
| 2 | Instruction number | 2 |
| 4 | Type | 1 |
| 5 | Flags: bit 0 keep the Wells' Paradigm state | 1 |
| 6 | Dark (non-zero = dark) | 1 |
| 7 | Frequency Hz, PulseWidth ms | 2 + 2 |
| 11 | EventGapMs | 2 |
| 13 | Acclimation N | 2 |
| 15 | Settings, 5 × uint32 by type: ClosedLoop `HoldMs, MaxOnMs`; FixedInterval `ActivationMs, LockoutMs`; NonFeeding `OnDelayMs, MaxOnMs`; ProgressiveRatio `ActivationMs, Series (0 Arithmetic, 1 Exponential), FirstRequirement or Scale×1000, Step or Rate×1000, Cap (0 = 65535)`; FixedRatio `ActivationMs, Ratio` | 20 |
| 35 | Thresholds per Well, 0-1023 after baseline; 0xFFFE On, 0xFFFF Off | 12 × 2 |
| 59 | Checksum | 4 |

Other commands: 0xFC status (records, needs ACK 0xFA or partial ACK 0xF9), 0xEA latest record, 0xEB version string (`4.0.0`), 0xFE buffer reset (also resets Paradigm state and Activations), 0xFB linkage. The old instruction 0xFD is NACKed by 4.0.0.

### 11.3 Golden values

- The shared golden instruction (`GOLDEN_INSTRUCTION` in `PyMCU/tests/test_protocol.py`): DFM 5, number 258, ProgressiveRatio, keep-state, dark, 40 Hz, 8 ms, gap 100, Acclimation 3, `ActivationMs 500, Arithmetic, FirstRequirement 1, Step 10, Cap 200`, thresholds `20, On, Off, 30, 1023 × 8`.
- `Record()` in the same file builds a valid 127-byte record from keyword values; copy its layout for byte-level fixtures.
- Exponential series defaults: 1, 2, 4, 6, 9, 12, 15, 20, 25, 32, 40, 50, 62, 77, 95.
- Arithmetic `FirstRequirement 1, Step 2, Cap 5` → Activations at Events 1, 4, 9, 14 (Requirements 1, 3, 5, 5).
- FixedRatio `Ratio 3` → Activations at Events 3, 6, 9.
- Acclimation 3 → exactly 3 Activations in Phase `A`, each lasting contact + `ActivationMs`; the first Main Activation then needs `Requirement` k = 1.
- `OnMs` saturates at 255; a linked Well's `OnMs` equals the trigger Well's while its `Activations` stays 0.
