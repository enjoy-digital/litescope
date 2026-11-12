# Embedded logic analysis in a nutshell {#la-primer}

This chapter explains embedded logic analysis to an FPGA engineer who has never used an
analyzer inside a chip. It builds the vocabulary of a capture: probes, samples, depth, triggers,
windows, subsampling and compression, then the clocking, the cost and the way samples reach the
host. It ends with a method for using captures well.

Each section starts with the idea and ends with the part of LiteScope that implements it. Parts II
and III then give the details, and link back here for the concepts. The waveforms of this
chapter are drawn illustrations; [Getting started](#getting-started) shows a real capture.

## External and embedded analyzers {#primer-embedded}

A bench logic analyzer has probes that clip onto pins or connectors. It sees only what reaches
the board, so the internal signals of an FPGA must be routed to spare pins first: a rebuild per
signal set, on boards that have few spare pins. An embedded analyzer is gateware placed next to
the design: it samples internal nets directly, at the clock of the design, and stores the samples
in the memory of the FPGA.

The table below compares the two approaches.

| Aspect | External analyzer | Embedded analyzer |
|----------------------|-----------------------------------|--------------------------------------|
| Signals seen | Pins routed out of the FPGA | Any net of the design |
| Width | Number of probe channels | Number of probe bits, set at build time |
| Sample clock | The analyzer's own clock | A clock of the design |
| Memory | In the instrument, large | Block RAM of the FPGA, small |
| Cost to the design | Pins and a rebuild per signal set | Block RAM, logic and timing margin |
| Changing the probes | Rewire, or route other signals out | Rebuild the bitstream |

FPGA vendors provide embedded analyzers with their tools: AMD ILA, Intel SignalTap, Lattice
Reveal. LiteScope does the same job in plain LiteX gateware, so the same probes and host tools
work on every FPGA family and in simulation.

## Probes, samples and depth {#primer-samples}

A *probe* is one signal given to the analyzer: a bit, a bus, an FSM state. All probes of a
capture are concatenated into one wide word, the *sample*, taken at every rising edge of the clock
of the probes. Its width is the sum of the probe widths.

The samples go to a memory of *depth* words. The depth and the clock period set the time window
of a capture: depth x clock period x subsampling factor. At 100 MHz, 1024 samples cover
10.24 µs; with one sample kept every 1000 cycles, they cover 10.24 ms.

The memory is the main cost of an analyzer: its size is the depth times the sample width. Wide
samples and deep memories use block RAM fast, which is why a capture probes few signals.

In LiteScope, the probes are given as a *group*, a list of signals. An analyzer can hold several
groups, selected at run time by a register, so one bitstream can look at different parts of the
design. The sample is as wide as the widest group. See [Analyzer
architecture](#analyzer-architecture).

## Triggers: mask and value {#primer-trigger}

Memory is small, so an analyzer must start storing at the right moment. The *trigger* is the
condition that marks this moment. The simplest condition compares the sample with an expected
value, but only on the bits that matter: a *mask* selects these bits, and the other bits are
*don't care*.

The figure below shows one comparison. The term matches when every selected bit of the sample
equals the corresponding bit of the value; the bits outside the mask are ignored.

![One trigger term on an 8-bit sample: the mask selects bits 7 to 4, the value expects `1011` on
them; bits 3 to 0 are don't care, so the term matches.](primer_trigger.svg)

Such a mask and value pair is a *term*. One term can test several probes at once: each probe adds
its bits to the mask and its expected value to the value, so the probes are ANDed. The driver
cuts each value to the width of its probe ([Trigger](#trigger)).

In LiteScope, the driver builds terms from probe names and values given as strings: `"0x12"`,
`"0b1x0"` with `x` as a don't care bit, or `"0x1x"` with `x` as a don't care hexadecimal digit.
See [Trigger](#trigger).

## Sequences and edges {#primer-sequence}

One term catches a value. A *sequence* of terms catches an order of events: the analyzer waits
for the first term, then for the second from the next sample on, and so on. It fires when the
last term matches, as the figure below shows. The matches need not be adjacent.

![A sequence of two terms on an 8-bit probe: the analyzer waits for `0x01`, then for `0x02`; the
`0x02` seen before the first match does not count. The trigger fires on the second match. Drawn
without the pipeline delays of the gateware.](primer_sequence.svg)

An *edge* is a sequence of two terms. A rising edge on a bit is the term "bit is 0" followed by
the term "bit is 1": the first 1 after a 0 is a rising edge. A falling edge is the reverse.

With no term at all, the analyzer fires at once: this is an *immediate capture*, which shows
what the probes are doing now.

In LiteScope, the gateware holds a short list of terms and matches them in order; it has no edge
detector. The driver turns an edge request into its two terms (`add_rising_edge_trigger`,
`add_falling_edge_trigger`). The helpers are meant for one-bit probes: on a wider probe the two
terms compare the whole probe with 0 and with 1. See [Trigger](#trigger).

## Pre-trigger and post-trigger windows {#primer-window}

The cause of a problem often comes before its symptom, so an analyzer keeps samples from before
the trigger too. Once armed, it writes every sample into its memory and, until the trigger,
keeps only the most recent ones: the oldest samples are dropped as new ones come in. These kept
samples form the *pre-trigger window*.

When the trigger fires, the analyzer keeps storing until the capture holds its full length, then
stops. The figure below shows the two windows on the time axis and in the memory.

![Capture window. Before the trigger, only the most recent samples are kept, up to the pre-trigger
window set by `offset`; after it, the memory fills up to the capture `length`, which is at most
the `depth`.](primer_window.svg)

If the trigger fires before the pre-trigger window is full, the capture holds fewer samples from
before the trigger. Arm the analyzer early enough, or reduce the window. The arming itself takes
`depth` clock cycles, during which the trigger compares nothing: an event in that time is not
seen ([Flush and arming](#stor-flush)).

In LiteScope, the pre-trigger window is set by the `offset` argument of the driver's `run()` and
the capture length by its `length` argument. The trigger sample is at index `offset` of the
uploaded samples; [Trigger position in the capture](#trig-position) gives the details.

## Subsampling {#primer-subsampling}

Some events last milliseconds, far longer than the memory can cover at the full clock rate.
*Subsampling* keeps one sample every N clock cycles, which multiplies the time window by N for
the same memory.

The price is resolution. A pulse that starts and ends between two kept samples is never stored,
as the figure below shows. Subsample only signals that are stable over N cycles, such as state
machines and slow status bits.

![Subsampling by 4: one sample is kept every 4 clock cycles (S0 to S2). The slow signal is seen;
the short pulse falls between S1 and S2 and is missed.](primer_subsampling.svg)

In LiteScope, the trigger looks at every clock cycle and subsampling applies after it: the
trigger never misses a short event, even when the sample that matched is not stored. See
[Subsampler and run-length encoding](#subsampler-rle).

## Run-length encoding {#primer-rle}

Probed signals are often idle: a bus waits, a state machine stays in one state. *Run-length
encoding* (RLE) stores a run of identical samples as one sample followed by a count, instead of
storing every copy. The figure below compares the two.

![Run-length encoding of nine samples: six `A`, two `B`, one `C`. Raw storage uses nine words;
RLE stores each first sample raw and each run as a repeat word, five words in
all.](primer_rle.svg)

A marker bit tells a raw sample from a repeat word, so each word is one bit wider. One repeat word
holds a limited count, so a long run takes several. When every sample differs from the previous
one, RLE stores one word per sample and saves nothing: this is the worst case.

In LiteScope, RLE is a build option (`with_rle`), enabled per capture by the driver. It applies
after the trigger: the pre-trigger window is stored raw. The driver expands the words back into
samples. See [Subsampler and run-length encoding](#subsampler-rle).

## Clock domains {#primer-clocks}

A design has several clocks, and a signal is only stable relative to its own clock. The analyzer
must sample the probes in their own clock domain; sampling them with another clock would capture
them mid-transition.

The host side runs on the bus clock of the SoC. Only the control registers, the trigger terms
and the stored samples cross between the two domains, through synchronizers and small FIFOs.
The probes never cross.

A fast domain is the hard case. The analyzer's comparator and memory then run at that clock, and
a wide analyzer in a fast transceiver domain can fail timing and return wrong samples. Keep the
analyzer in one domain, preferably the system clock, and its width under about 128 bits.

In LiteScope, the `clock_domain` argument selects the domain of the probes, called the *scope
clock domain*, `sys` by default.
[Analyzer architecture](#analyzer-architecture) lists every crossing.

## Observing changes the design {#primer-observer}

An embedded analyzer is part of the bitstream. Adding it changes the placement and the routing,
and its comparator and memory load the probed nets. A timing-sensitive bug can move or vanish
when the analyzer is added, and a design that met timing may no longer meet it.

Keep each capture narrow: few probes, the depth that the question needs, in the domain of the
signals. Check the timing report of every build with an analyzer, as for any other change.

## Getting the data out {#primer-bridges}

The analyzer is controlled through registers on the bus of the SoC: the host writes the trigger
terms, arms the capture, polls for completion, then reads the memory back through one 32-bit
data register, one read per 32 bits of each word. Any link that gives the host access to that bus will do.

In a LiteX SoC, a *bridge* turns a host link into bus accesses: UARTBone on a serial port,
JTAGBone on the JTAG cable, Etherbone on Ethernet, or the PCIe core. On the host, `litex_server`
opens the link and serves the bus on a TCP port; the CLI and the driver connect to it, as the
figure below shows.

![Getting data out: the CLI or the driver talks to `litex_server` over TCP; `litex_server`
drives one bridge of the SoC, which turns the requests into bus accesses to the analyzer
registers.](primer_bridges.svg)

The bridge sets the upload time, not the capture: the capture always runs at the scope clock. A
UART bridge is the slowest and an Ethernet or PCIe bridge the fastest. The same capture works on
any of them. See [Adding LiteScope to a SoC](#integration).

## Waveform files and viewers {#primer-formats}

The uploaded samples are written to a file that a waveform viewer opens. The usual formats are:

- VCD (Value Change Dump), the text format of HDL simulators, opened by GTKWave;
- the sigrok session format (`.sr`), opened by PulseView;
- CSV, JSON or Python, for scripts that check a capture without a viewer.

In LiteScope, the driver's `save()` picks the format from the file extension, and adds a clock
and a trigger marker, set at the trigger sample, to the waveform. See [Capture files](#file-formats).

## A method {#primer-method}

A capture answers one question well. Before probing, read the status registers of the design:
counters and state registers often answer the question without a capture, and they cost
nothing. When a capture is needed, choose the narrowest set of probes and a trigger on the event
itself, not on a time.

Then iterate: one capture, one observation, one change of trigger or probes. Captures are cheap
to repeat from a script, so a rare event can be caught by re-arming until it happens. [Debugging
LiteScope itself](#debugging) covers the cases where the capture itself goes wrong.

## Where to go next {#primer-next}

[Analyzer architecture](#analyzer-architecture) describes the gateware;
[Getting started](#getting-started) runs a first capture in simulation.
