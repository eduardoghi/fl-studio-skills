# FabFilter Pro-Q 4

Observed in REAPER 7.86, VST3, set through `fx.set_param` by the text each parameter shows.

## Parameters

- Each band shows as `Band N Used`, `Shape`, `Frequency`, `Q`, `Slope`, `Stereo Placement` and `Gain`. The gain is
  normalized as 0.5 + dB / 60, so 0.5 is 0 dB and the range is ±30 dB.
- `Slope` applies to the cut shapes and reads as text such as `12 dB/oct`.

## Cut filters aren't Butterworth at the default Q

A `Low Cut` at 12 dB/oct with `Q` 0.71 was measured on renders, as the transfer function between the input and the
output. At 28 Hz and again at 35 Hz the curve kept the same shape relative to the set frequency:

| Frequency relative to the set one | 0.7x | 1x | 1.4x | 1.8x | 2.5x | 3.6x | 7x |
|---|---:|---:|---:|---:|---:|---:|---:|
| Level | −9 dB | −6 dB | −3.5 dB | −2.3 dB | −1.3 dB | −0.65 dB | −0.17 dB |

- The set frequency is the −6 dB point, not −3 dB, and the slope reaches about three octaves above it. A Butterworth
  high-pass at the same frequency would be −3 dB there and under −0.1 dB an octave and a half above.
- **Effect on a drum part.** A cut meant for the sub, set at 35 Hz, took 2.1 dB from 60-100 Hz and 0.6 dB from
  100-150 Hz.
- **Effect on a whole mix.** At 28 Hz it took 0.45 LU, against 0.07 LU for removing everything below 35 Hz with a
  steep zero-phase filter.
- **Phase.** It turned the phase by 90 degrees at the set frequency and 30 degrees at 3.6x.
- **What to do.** Measure the response on a render before calling a cut sub-only. For a cut that leaves the low end
  above it alone, try a higher Q or a steeper slope and measure again. Those settings weren't measured here.
