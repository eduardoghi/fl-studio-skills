# Archetype Cory Wong X (Neural DSP)

Observed in REAPER 7.86 on a sampled clean guitar DI, measured over one bar. The manual wasn't read for this note.

- Every section is a host parameter, about 150 named ones. `Amp Type` and `Cab Type (Unlinked)` take `Funk`, `Clean`
  and `Snob`, with `Snob` as the default and `Amp/Cab Linked` off. The compressor `The 4th Position Comp` starts on.
- The default chain scoops the mids. Measured as shares of the energy from 80 to 4800 Hz, the DI had 27% from 300 to
  600 Hz and 19% from 600 to 1200 Hz, and the default Amp Snob chain (compressor off, Bright on) had 12% and 7%.
  Switching sections off one at a time showed where it happened. The amp alone took those bands to 6% and 7% and put
  45% above 2.4 kHz, and the default cabinet (ribbon microphone) alone kept the lows and cut nearly everything above
  1 kHz. Bright and the EQ section only moved energy between the lows and highs.
- The `Clean` amp with its cabinet was darker still, with 69% below 300 Hz.
- A spectral centroid close to a reference hid that scoop, since lows and highs averaged out. Compare band shares.
- The amp brought the crest factor from about 20 dB on the DI to about 13 dB.
