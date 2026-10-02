# Data sources and rights

Rule: no data goes into training, and no weights trained on it ship, until its row below says "allowed". Unknown means not allowed.

| Source | Content | License (as found 2026-10-02) | Weights trained on it may ship commercially? | Status |
|---|---|---|---|---|
| NAMAA's transcribed Saudi podcasts (~30 h, used for NAMAA-Saudi-ASR-V1) | Saudi podcast speech with human transcripts | Unknown to this project; the adapter is Apache-2.0 | Unknown: rights to the **audio**, not only the transcripts, are unconfirmed | not allowed until confirmed |
| SADA22 (`MohamedRashad/SADA22`) | Saudi dialect TV speech | CC-BY-NC-SA-4.0 | No (non-commercial) | not allowed |
| SDAIA Saudilang Code-Switch Corpus (`SDAIANCAI/Saudilang-Code-Switch-Corpus`) | Saudi code-switching | CC-BY-SA-4.0 | Possibly, but share-alike may apply to derivatives; needs a legal check | not allowed until a legal check |
| Other Saudi podcast sets on Hugging Face | Podcast speech | No license listed in several cases | Unknown | not allowed until clarified |
| Own recordings | Consented read and spontaneous Saudi speech | Ours | Yes, if the consent covers commercial model training | allowed once such consent is recorded |

## TTS voices

Each voice added needs a recorded consent from the speaker covering model training and commercial release. Record it here.

| Voice | Speaker consent | Allowed uses |
|---|---|---|
| `af_msa` (Nabra-Saudi, single female voice) | Not documented in the model card | Model weights are Apache-2.0 |
