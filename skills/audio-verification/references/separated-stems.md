# Separated stems as targets

Read this when separated stems are used as a target, to judge what a residual stem holds, or to compare a rebuild's
parts with the original's stems.

A separator's stems are a guess about the instrumentation, and a processed instrument can be split across several.
These checks come from one mix with a stereo processed guitar, a residual "other" stem and vocals.

- Compare the same stem across separators. Two estimates of the guitar agreed to 8 to 19 dB (SDR between them), while
  the two "other" stems agreed to about 0 dB, which means each separator put something different there. The sum of
  guitar, other and piano agreed better across three separators than the guitar alone (15 to 27 dB against 8 to 19),
  most in the loudest section. Where that happens, the split is arbitrary and the sum is the more reliable target for
  pitch and level, at the cost of including whatever else fell into those stems.
- Mid and side can tell different stories. The "other" stem was louder in side than in mid, with negative left-right
  correlation, and its side carried a harmony that both separators extracted alike (chroma 0.82 to 0.91 between
  them) but that differed from the guitar's at the same moment.
- Test where a residual stem comes from against each other stem, not only the obvious one. For each candidate source,
  correlate the residual's envelope with the source's envelope smoothed by exponential decays of a few T60 values,
  and its chroma with the source's chroma integrated over the past. A reverb or delay tail correlates better as the
  smoothing grows. A part split by the separator correlates at once. In one section the residual followed the
  vocals' harmony and their smoothed envelope, so it was the vocals' reverb or delay, not an instrument. In another
  it followed the guitar's envelope in sync.
- Run the separator on a mix you built, with known parts, before blaming the reference's stems on an effect. A
  guitar with a short stereo reverb and, separately, with a long dark tail added went 97 to 99% into the guitar stem,
  tail included, and the "other" stem stayed 54 dB or more below. Those effects couldn't produce the reference's
  residual, which pointed to a source the model doesn't call guitar.
- To find what a mix holds beyond the parts already rebuilt, run the same separator with the same settings on the
  rebuild and compare each leftover stem bar by bar, as its level against the mix it came from. The rebuild's stems
  show how much the separator leaks from the known parts, and what the original's stems hold above that is evidence
  of a missing layer. That avoids reading the residual between the mix and the rebuild as a stem, which would carry
  every difference in phase, tone and playing. On one song the "other" stem sat 12 to 40 dB under the mix while the
  rebuild's sat 58 to 79 dB lower than that, and the "vocals" stem was empty in both.
- When extra attacks in a stem suggest a missing part, count the same test the other way too, the rebuild's attacks
  with no match in the original. That count is a reference for the detector's disagreement, not an exact measure of
  its error, since it can hold real differences in playing too. Repeat old evidence against the current rebuild,
  since it may have been measured against an earlier version. A rhythm part once read as a 16th-note stream missing
  from the transcription left 182 extra attacks in the original's guitar stem against 157 the other way, and on the
  offbeats fewer than the rebuild's (95 against 109). Two other separators and the mix gave the same balance, and the
  16th-note autocorrelation was near zero in both. The approved guitar already covered what the old transcription
  had missed.
- Before reading a quiet layer's stem level as missing content, calibrate how the separator treats your own version
  of it. Separate the layer alone, the rebuild without it, and the rebuild with it at a few gains (offline sums of the
  same renders), and project each stem onto the layer's signal. A pad alone went whole into "other" in three
  separators. Mixed with the guitar, one separator put nearly all of it in the guitar stem (−74 dB reached "other"),
  and another kept −7 to −36 dB of it in "other" depending on the section. The response wasn't linear either, since
  +6 dB of pad raised "other" by 7 to 18 dB. Stem differences of 14 to 31 dB came down to a pad 2 to 11 dB too quiet
  once calibrated. Compare the layer with the original's stem directly as well, and treat the two results as the
  ends of a range rather than a gain.
- Drum tuning shows up in a chroma. A pitch class 13 to 18 % stronger in the original's mix sat entirely in its drum
  stem, a kick or toms an octave above the rebuild's. Compare chroma above about 200 Hz, or per stem, before taking
  such a difference for missing notes.
- To tell a doubling from an independent layer, check whether its attacks fall on the known part's notes more often
  than chance, and where its energy sits relative to each note (same pitch, an octave up). Run the same test on the
  known part's own stem, since a part's harmonics put energy an octave up too. A "piano" stem had 73 to 79% of its
  attacks on guitar notes (22 to 27% by chance) and its energy an octave above them, while both guitar stems had
  similar energy at the pitch and an octave up, so it was a layer doubling the line an octave higher.
- Compare width section by section and band by band, with the left-right correlation and the level lost in mono,
  before copying a stem's width. A pad stem had its side 6 to 11 dB over its mid below 300 Hz in some sections and
  not in others. A mid and side chain that copied that width everywhere lost 8.3 dB in mono where the plain patch
  lost 3.1, so the widening fits as automation per section in the mix rather than a fixed chain.
- A stem's name doesn't identify the instrument of a layer that doubles another part. Calibrate it by mixing known
  sources into the rebuild and separating again. Real piano and electric piano patches playing with a guitar, at the
  level of the original's "piano" stem, went 73 to 100% into the guitar stem, and even 20 dB louder the piano stem
  stayed 40 dB or more under the mix. The original's piano stem held something none of them reproduced, so the stem
  showed content the rebuild was missing, not that an independent instrument existed or which one.
- A stem can lose part of an instrument's harmonics to other stems. Before EQ, saturation or other effects chase the
  whole spectral difference to a stem, compare with the mix and with other separators. A bass stem stayed darker
  than every rebuild, and that remainder was left alone rather than taken as the instrument's tone, without proof
  either way.
- To get a known part for such a test, export each part alone from the same project with the others muted and add
  them offline. Subtracting an earlier render fails when the instrument isn't sample-identical between renders, as
  with round robin samples or modulated effects.
