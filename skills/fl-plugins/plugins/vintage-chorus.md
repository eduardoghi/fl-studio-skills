# Vintage Chorus

Models the bucket-brigade chorus of the Roland Juno-6 (manual).

## Watch out

`Noise` is on by default, and one wheel step below the default read -66.3 dB. It emulates the hardware's hiss, and the
chorus LFO modulates it (manual). On a guitar track at 0.9 fader this kept a floor near -62 dBFS after the music ended,
heard as a slow wave at 0.8 Hz, and FL's tail detection stretched a 20 s render to 50 s (observed).

Set `Noise` to 0 unless the hiss is wanted. To keep it, `Noise gate` silences it while nothing plays (manual).

## Controls

| Name in the API | What it does |
|---|---|
| `Mode` | Chorus I or II copy the hardware and switch off the modulation and LFO panels. Edit unlocks some parameters |
| `Mix` | Dry and wet balance. Starts at 50% (observed) |
| `Noise`, `Noise gate` | Added hiss and the gate for it |
| `Time 1`, `Time 2` | The two delay times the chorus moves between |
| `Feedback` | Not on the hardware. Makes it more flanger-like |
| `High pass` | Cuts lows on the wet signal only |
| `LR Phase` | Phase between the two LFOs. More offset gives more width |
| `Mono input` | Sums the input to mono first |

`Speed` reads 0.00 Hz in Chorus 1 (observed), which is expected, since the LFO panel is inactive in that mode.
Shift+click on a disabled mode runs I and II together (manual).

## Values used

Mode I, with `Mix` at 35% on a clean arpeggio and 42% on a distorted part.
