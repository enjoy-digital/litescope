```{=latex}
\part{The core}
```

```{=html}
<h1 class="part">Part II. The core</h1>
```

# Analyzer architecture {#analyzer-architecture}

This chapter describes the analyzer as a whole: its parameters, the pipeline that carries the
probes to the sample memory, the probe groups, the clock domains and the sequence of a capture.
Read it before adding the analyzer to a design. The concepts are introduced in [Embedded logic
analysis in a nutshell](#la-primer).

## At a glance {#arch-glance}

| Parameter | Default | Meaning |
|-------------------------|------------------------|------------------------------------------|
| `groups` | required | A signal, a list, or a dictionary of lists, one per group |
| `depth` | required | Words of the sample memory |
| `samplerate` | `1e12` | Written to `analyzer.csv` for the dumps; no effect on the hardware |
| `clock_domain` | `"sys"` | Domain whose clock samples the probes |
| `trigger_depth` | `16` | Depth of the term memory, a power of two of at least 4; the memory holds one more term |
| `subsampler_width` | `16` | Width of the subsampler counter |
| `register` | `False` | One register stage on the probes before the mux |
| `with_rle` | `False` | Builds the run-length encoder |
| `rle_length` | `256` | Longest run held by one RLE word, at least 2 |
| `csr_csv` | `"analyzer.csv"` | Configuration file for the host; `None` skips it |

The analyzer is one class, `LiteScopeAnalyzer`, built with these parameters. Each block has its
own chapter: [Trigger](#trigger), [Subsampler and run-length encoding](#subsampler-rle) and
[Storage and read-back](#storage). The [status](#intro-status) of each feature is given in the
introduction.

## Pipeline {#arch-pipeline}

The probes travel through a chain of stream blocks, from the selected group to the sample memory,
as the figure below shows. Every block handles one sample per cycle of the scope clock. The host
reaches each block through its registers on the register bus.

![Analyzer pipeline. Follow the samples from left to right: the mux selects a group, the trigger
marks the samples after its condition, the subsampler keeps one sample in N, the optional RLE
compresses repeated samples and the storage keeps the window around the trigger.](arch_pipeline.svg)

The order of the blocks sets what each one sees:

- **Mux**: selects one group of probes.
- **Trigger**: compares every sample with its terms, before any subsampling.
- **Subsampler**: keeps one sample every N cycles, after the trigger decision.
- **RLE**: replaces runs of identical samples by repeat words, only after the trigger.
- **Storage**: keeps the pre-trigger window, then fills the memory up to the capture length.

### Sample stream {#arch-stream}

Between the blocks, a sample is a stream word with two fields: `data`, the probes of the group,
and `hit`, a flag set by the trigger. The mux asserts `valid` on every cycle, so the stream never
stops: the analyzer sees the probes continuously and never applies back-pressure to the design.

The trigger sets `hit` on every sample after its last term has matched. The storage looks at
`hit` to leave its pre-trigger phase, and the RLE starts compressing at the same moment. The
`hit` flag itself is not stored.

## Probe groups {#arch-groups}

A group is a list of probes captured together. `groups` accepts a single signal, a list, or a
dictionary such as `{0: group_a, 1: group_b}`. Anything other than a dictionary becomes group 0.
The keys of a dictionary must be the numbers 0 to N-1, since they index the inputs of the mux.

Each entry of a group can be one of these kinds:

| Probe | Captured as |
|----------------------|---------------------------------------------------------------|
| `Signal` | The signal itself |
| `Record` | Its fields, flattened into signals |
| `FSM` | Its state signal, with the state names exported for the dumps |
| Slice of a signal | A new signal named `<name>_<bit>` or `<name>_<msb>_<lsb>` |
| Other expression | A new signal named `expr`, driven by the expression |

A signal that appears twice in a group is kept once; a slice or an expression given twice is
captured twice, since each one becomes a new signal. The first probe of a group takes the least
significant bits of the sample, and each following probe sits above the previous one.

The sample width, `data_width`, is the width of the widest group. Narrower groups are padded with
zeros up to that width, so every group costs the same memory width. The group register,
`mux_value`, has `bits_for(N)` bits for N groups.

The host selects a group before a capture. A value of `mux_value` that names no group connects
nothing: no sample reaches the trigger or the storage, and the capture never completes. The
driver does not check the value.

The analyzer writes the groups, the width of each probe and the state names of the FSMs to
`analyzer.csv` when the design is elaborated. The host tools read this file to find each probe in
the sample; [Capture files](#file-formats) describes its rows.

## Register stage on the probes {#arch-register}

With `register=True`, each group goes through one register in `clock_domain` before the mux. The
register cuts the timing path between the probed logic and the analyzer, at the cost of one
flip-flop per probe bit. All the probes move by one cycle together, so their relative timing is
unchanged.

## Clock domains {#arch-clocks}

The analyzer runs its pipeline in its own domain, `scope`, whose clock is the clock of
`clock_domain`. The probes are sampled in the domain where they live, without any crossing. The
reset of `scope` is not driven: the blocks start from their initial values and the register
writes of the driver bring them back to idle.

The registers stay in `sys`, the domain of the register bus. The figure below shows the four
kinds of crossings between the two domains.

![Clock domains of the analyzer. Look at the four crossings: control values and status flags go
through MultiReg synchronizers, while the trigger terms and the captured words go through
asynchronous FIFOs.](arch_clocks.svg)

| Crossing | Direction | Carries |
|------------------------------|--------------|------------------------------------------------|
| `MultiReg` | sys to scope | Trigger enable, group, subsampling, RLE enable, storage enable, length, offset |
| `AsyncFIFO`, `trigger_depth` | sys to scope | Trigger terms (mask and value) |
| `MultiReg` | scope to sys | Trigger done, storage done, memory level, FLUSH state of the storage |
| `AsyncFIFO`, 4 words | scope to sys | Captured words on their way to `mem_data` |

The multi-bit values (group, subsampling, length, offset, memory level) cross through a plain
`MultiReg`, without Gray coding. The control values are written before the capture is armed and
stay constant during it. The memory level changes while the capture runs: read it once the
capture is done, as the driver does. The read path, in `sys`, also uses `storage_enable` directly,
without crossing: the read path pops words while it is 0.

With `clock_domain="sys"`, both domains share one clock and the crossings only add a few cycles
of delay. A fast domain, such as the clock of a transceiver, puts the comparator and the memory
in that domain too; [Adding LiteScope to a SoC](#integration) gives the rules for choosing it.

## Capture sequence {#arch-capture}

The driver runs a capture with register writes, and the storage state machine answers with its
`done` flag. The figure below shows the steps of one capture, as the driver methods `run()`,
`wait_done()` and `upload()` perform them.

![One capture. Read the steps from left to right: the driver disarms the trigger and loads the
terms, arms the storage then the trigger, here after the flush as over a slow bridge; the storage
waits for hit, fills up to the capture length and raises done; the driver then uploads the words.
Not to scale.](arch_capture.svg)

1. **Disarm**: write 0 to `trigger_enable`. The trigger drops the terms left in its memory and
   the driver polls `trigger_done` until the memory is empty.
2. **Load terms**: for each term, write `trigger_mem_mask` and `trigger_mem_value`, then
   `trigger_mem_write`. Once a term is loaded, `hit` goes low.
3. **Arm storage**: write `storage_offset` and `storage_length`, then 0 and 1 to
   `storage_enable`. The rising edge starts the flush of the memory.
4. **Arm trigger**: write 1 to `trigger_enable`. The trigger compares samples from now on. With
   fast register writes, this happens before the flush ends, a case described in [Limitation:
   match during the flush](#stor-flush).
5. **Pre-trigger**: the storage keeps the last `offset` words while it waits for `hit`.
6. **Post-trigger**: after the match, the storage fills up to `length` words and returns to idle.
7. **Done and upload**: `wait_done()` polls `storage_done`; `upload()` reads `storage_mem_level`,
   then that many words from `storage_mem_data`, four fewer than the capture length
   ([Upload](#stor-upload)).

The trigger steps are described in [Trigger](#trigger) and the storage steps in [Storage and
read-back](#storage). The driver, its options and the dumps it writes are described in [Host
tools](#host-tools).

## In the code {#arch-code}

| Class | Role (all in `litescope/core.py`) |
|------------------------|----------------------------------------------------------------|
| `LiteScopeAnalyzer` | Parameters, groups, `scope` domain, pipeline, `analyzer.csv` |
| `_Mux` | Group selection (`mux_value`) |
| `_Trigger` | Term memory and comparator |
| `_SubSampler` | Subsampling counter |
| `_RLE` | Run-length encoder |
| `_Storage` | Sample memory and read path |
| `core_layout` | Stream layout: `data` and `hit` |

The driver side is `LiteScopeAnalyzerDriver`, in `litescope/software/driver/analyzer.py`.

Where to go next: [Trigger](#trigger) for the conditions, [Storage and read-back](#storage) for
the capture window, [Adding LiteScope to a SoC](#integration) to build an analyzer into a design.
