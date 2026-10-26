# PipeWire notes (verified on PipeWire 1.4.2, WirePlumber 1.4.2, Debian 13 / KDE Wayland)

Spike configs live in `spike/` (`phase0.conf`, `phase0_test.conf`, `phase0_linear.conf`).

## Running a filter-chain as a child process

`pipewire -c /abs/path/chain.conf` works with a self-contained config. Besides the
`libpipewire-module-filter-chain` entry it needs the usual client modules:

```
context.spa-libs = {
    audio.convert.* = audioconvert/libspa-audioconvert
    support.*       = support/libspa-support
}
context.modules = [
    { name = libpipewire-module-rt args = { } flags = [ ifexists nofail ] }
    { name = libpipewire-module-protocol-native }
    { name = libpipewire-module-client-node }
    { name = libpipewire-module-adapter }
    { name = libpipewire-module-filter-chain args = { ... } }
]
```

The chain creates two nodes:
- `capture.props.node.name` (e.g. `onyx_eq`), `media.class = Audio/Sink`: the virtual sink apps play into.
  **This is the node that owns the filter controls.**
- `playback.props.node.name` (e.g. `onyx_eq.output`), `Stream/Output/Audio`: links to the hardware sink.

The nodes appear in `pw-dump` ~0.3–1 s after the process starts.

## Live control changes

Syntax that works (on the **sink/capture** node id):

```
pw-cli set-param <sink-id> Props '{ params = [ "band_0:Gain" 12.0 "band_0:Freq" 120.0 ] }'
```

- Several controls can be batched in one `params` list.
- With `audio.channels = 2` the graph is duplicated per channel; one `set-param` updates both
  (measured: identical response on FL and FR).
- Current values are readable in `pw-dump <id>` → `info.params.Props[*].params` (the entry whose
  first key starts with a node name; another `params` entry holds channelmix props).
- **Throughput:** spawning `pw-cli` per update is too slow for 60 Hz. A single long-lived `pw-cli`
  process (no args) accepts commands on stdin, one per line: 120 `set-param` lines were written in
  <1 ms and the final value landed. Send `quit\n` to exit (EOF alone does not exit it).
  Its stdout is very chatty — send it to `/dev/null`, or the pipe fills and blocks.

## Biquad maths (matches the app's `core/biquad.py`)

`spa/plugins/audioconvert/biquad.c` (used by the filter-graph builtins) is the RBJ Audio EQ Cookbook,
with `w0 = pi * freq / nyquist` and `alpha = sin(w0) / (2Q)` for every type, including shelves
(shelves use Q directly, not slope S). `A = 10^(gain/40)`. Bandpass is constant 0 dB peak gain.

Measured with white noise through `bq_peaking` 100 Hz +12 dB Q1 and 1 kHz −6 dB Q1 into a null sink
and recorded via `pw-record -P '{ stream.capture.sink = true }'`:

| f (Hz) | measured | model |
|---|---|---|
| 52.7 | +4.41 | +4.38 |
| 99.6 | +11.74 | +11.93 |
| 199 | +3.71 | +3.73 |
| 498 | −1.21 | −1.21 |
| 1002 | −5.83 | −5.84 |
| 10002 | −0.05 | −0.05 |

### Neutral ("pass-through") settings per type, from the edge cases in biquad.c

| label | neutral |
|---|---|
| bq_peaking / bq_lowshelf / bq_highshelf | Gain 0 |
| bq_lowpass | Freq ≥ nyquist (cutoff clamps to 1 → z-transform 1) |
| bq_highpass | Freq 0 |
| bq_notch / bq_allpass | Freq 0 |
| bq_bandpass | Q 0 with 0 < Freq < nyquist |

These let any slot be disabled live without a reload.

Note: `biquad_set()` resets the filter history (`x1`, `x2`) on every coefficient change, so very
large parameter jumps can tick. Throttling to ~60 Hz with small steps per tick keeps it inaudible
in practice; verify by ear in Phase 4.

## Preamp

The `linear` builtin works: `{ type = builtin name = preamp label = linear control = { "Mult" = 1.0 "Add" = 0.0 } }`.
`preamp:Mult 0.5` measured −6.02 dB flat.

## Routing: WirePlumber smart filter (WirePlumber ≥ 0.5; verified on 0.5.8)

The first version made "Onyx EQ" the default sink. That broke volume: the virtual sink has its own
volume starting at 100%, so 100% on Onyx EQ meant whatever the hardware was set to (e.g. 50%).

Now the chain is a **smart filter**, set in `capture.props`:

```
filter.smart = true
filter.smart.name = "onyx-eq"
filter.smart.target = { node.name = "<hardware sink node.name>" }
```

- WirePlumber routes every stream headed for the target device through the filter
  (`app → onyx_eq → onyx_eq.output → device`). The device stays the default, so the desktop's volume
  slider keeps controlling the hardware.
- Streams already playing are moved into the filter when it appears, and straight back to the device
  when it disappears (including a crash), so stopping the EQ never leaves audio stranded.
- The filter is listed under Filters in `wpctl status`, not under Sinks.
- Change the target live (no reload) through the `filters` metadata, keyed by the filter's node id:
  `pw-metadata -n filters <id> filter.smart.target '{ "node.name": "<sink>" }' Spa:String:JSON`.
  Delete it when the node goes away (`pw-metadata -n filters -d <id> filter.smart.target`).
- WirePlumber's default-node selection does **not** skip filters. If `default.configured.audio.sink`
  is still `onyx_eq` (left over from the first version), the filter can become the default. The app
  resets the default to the real device at startup, and the device poll repairs it if it happens later.
- WirePlumber restores the filter's own volume by `media.name` (`stream-properties`,
  `Audio/Sink:media.name:Onyx\sEQ`). Since that volume is now hidden from users, the app sets it to
  1.0 and unmutes after every start. One install had a saved 0.125 (50% cubic, −18 dB).
- A recording stream aimed at the device's monitor is also redirected, to the filter's (pre-EQ)
  monitor. To measure post-EQ audio, create the recorder with `node.autoconnect = false` and
  `pw-link <device>:monitor_FL <recorder>:input_FL` (and FR) by hand.
- Default sink: `wpctl set-default <id>`; read it from the `default` metadata, key `default.audio.sink`.

## Test harness

A null sink for measurements:
`pw-cli create-node adapter '{ factory.name = support.null-audio-sink node.name = onyx_test_null media.class = Audio/Sink object.linger = true audio.position = [ FL FR ] }'`
(remove with `pw-cli destroy <id>`).
