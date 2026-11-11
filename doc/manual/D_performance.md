# Performance and resources {#performance}

This appendix gives the sizes that an analyzer adds to a design and the time windows it can
capture. Every figure is computed from the code and the parameters of the analyzer; the manual
gives no measured logic utilization or timing, since both depend on the device, the toolchain and
the rest of the design.

## Memories of the analyzer {#perf-memories}

An analyzer holds three memories, all declared by LiteX stream FIFOs. Each FIFO entry carries the
payload plus two framing bits (`first` and `last`), which the analyzer does not use. They are
declared in the Verilog, and the synthesis tool may remove them.

| Memory | Domain | Entries | Bits per entry |
|--------------------|----------------|------------------------|------------------------------------|
| Sample memory | `scope` | `depth` | `storage_width + 2` |
| Term memory | `sys` to `scope` | `trigger_depth`, plus one output register | `2 * data_width + 2` (mask and value) |
| Read-path FIFO | `scope` to `sys` | 4 | `storage_width + 2` |

The sample memory dominates and is the one that maps to block RAM. The two small FIFOs usually map
to distributed RAM or registers. The elaboration of the design of the register appendix
([Register reference](#registers)), with `data_width` 41, `with_rle=True` and a depth of 1024,
declares these three memories in its Verilog:

```verilog
reg [83:0] storage[0:15];      // term memory: 16 x (2*41 + 2)
reg [43:0] storage_1[0:1023];  // sample memory: 1024 x (42 + 2)
reg [43:0] storage_2[0:3];     // read-path FIFO: 4 x (42 + 2)
```

The comments are added here. The design is `_reference_soc()` of `doc/manual/registers.py`; a
LiteX `Builder` with `build(run=False)` writes its Verilog without running the toolchain.

## Sample memory of the example designs {#perf-examples}

The table computes the sample memory of the designs of [Examples and uses in the
ecosystem](#examples) with the formula above.

The last column divides by 36 Kbit, the size of a block RAM of the AMD 7-series and UltraScale
families: it is a lower bound, before the tool fits the width and the depth to the shapes of its
block RAMs.

| Design | `storage_width` | Depth | Bits (computed) | 36 Kbit blocks, at least (computed) |
|----------------------------|-----------------------|-------|---------------|----------------|
| Register appendix design | 42 | 1024 | 45 056 | 2 |
| `examples/arty.py` | 116 | 1024 | 120 832 | 4 |
| `litex_sim`, `--with-analyzer` | 204 | 512 | 105 472 | 3 |
| `test_sim.py`, `analyzer` | 32 | 64 | 2 176 | 1 |
| `test_sim.py`, `analyzer_rle` | 5 | 64 | 448 | 1 |

The widths come from the `analyzer.csv` of each design. Halving the probes about halves the memory
for the same depth: a narrow capture is cheaper and covers a longer time.

## Time window {#perf-window}

A capture of `length` words with a subsampling factor N, in a scope clock of frequency f, covers
`length * N / f` seconds, without RLE. The factor goes up to `2**subsampler_width`, 65536 with the
default width.

| Clock | Length | Subsampling | Window (computed) |
|-----------|---------|-------------|---------------------|
| 100 MHz | 1024 | 1 | 10.24 µs |
| 100 MHz | 1024 | 1000 | 10.24 ms |
| 100 MHz | 1024 | 65536 | 671 ms |
| 125 MHz | 4096 | 512 | 16.8 ms |

The last line is the subsampled capture of the USB3-PIPE manual
([Debugging](https://github.com/enjoy-digital/usb3_pipe/blob/master/doc/manual/14_debugging.md),
section "LiteScope captures"): 4096 samples of 512 cycles at 8 ns. Subsampling keeps one sample
every N cycles, so it suits levels and slow sequences; it loses pulses shorter than N cycles.

## Run-length encoding {#perf-rle}

With RLE, a run of N identical samples after the trigger takes `1 + ceil((N - 1) / (rle_length -
1))` words, and a sample that differs from the previous one takes one word. The worst case, a
probe that changes on every sample, stores one word per sample, as without RLE, in words one bit
wider.

| `rle_length` | Run of 256 samples (computed) | Run of 1024 samples (computed) | Most samples in 1024 words (computed) |
|----------------|--------------------|---------------------|-----------------------------|
| 256 (default) | 2 words | 6 words | 260 866 |
| 8 | 38 words | 148 words | 7 162 |

The last column is the case of one run filling the whole memory: one raw word, then 1023 repeat
words of `rle_length - 1` samples each. The pre-trigger window is stored raw, so a capture with a
large `offset` compresses less. `upload(max_samples=N)` caps the decoded samples
([Subsampler and run-length encoding](#subsampler-rle)).

The formula and the table are those of the encoding. On this revision the encoder drops one sample
at each repeat word and at each run end ([Limitation](#rle-limitation)): the counts above are
decoded samples, and the time a capture covers is longer by one cycle per repeat word.

## Register access and read-back {#perf-readback}

The upload reads `ceil(storage_width / 32)` registers per word: one for a capture up to 32 bits
wide, four for 116 bits.

The driver reads them in bursts of at most 192 registers at a fixed address, so a capture of
`length` words takes about `length * ceil(storage_width / 32) / 192` requests of the bridge. The
time of a request depends on the bridge and on `litex_server`.

## Timing {#perf-timing}

The analyzer adds paths of three kinds in `clock_domain`: the group multiplexer, the comparator of
`data_width` bits, fed by registers, and the write port of the sample memory. Their delay grows
with the width of the widest group. Keep groups well below 128 bits, prefer the system clock
domain, and use `register=True` when the probes come from far in the design ([Timing failures and
wrong clock domain](#debug-timing)).
