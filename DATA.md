# Data sources and rights

Rule: no data goes into training, and no weights trained on it ship, until its row below says "allowed". Unknown means not allowed yet. "TBD" rows need an answer from the data owner or a legal check.

Status key: **allowed** / **not allowed** / **TBD**

| Source | Content | License (as found 2026-10-02) | Weights trained on it may ship commercially? | Status |
|---|---|---|---|---|
| NAMAA's own transcribed Saudi podcasts (~30 h, used for NAMAA-Saudi-ASR-V1) | Saudi podcast speech with human transcripts | Unknown to this project; the adapter is Apache-2.0 | TBD: NAMAA must confirm it holds rights to the **audio**, not only the transcripts | TBD. **Owner:** NAMAA. **Next step:** written confirmation of audio rights from whoever holds the podcast agreements |
| SADA22 (`MohamedRashad/SADA22`) | Saudi dialect TV speech | CC-BY-NC-SA-4.0 | No (non-commercial) | not allowed |
| SDAIA Saudilang Code-Switch Corpus (`SDAIANCAI/Saudilang-Code-Switch-Corpus`) | Saudi code-switching | CC-BY-SA-4.0 | Possibly, but share-alike may apply to derivatives. Needs a legal check | TBD. **Owner:** project maintainer. **Next step:** ask a lawyer whether CC-BY-SA applies to model weights trained on it; until then do not train on it |
| Other Saudi podcast sets on Hugging Face | Podcast speech | No license listed in several cases | Unknown | not allowed until clarified |
| Own recordings (to be collected) | Consented read and spontaneous Saudi speech | Ours | Yes, if consent covers commercial model training | TBD. **Owner:** project maintainer. **Next step:** write a consent form that covers commercial model training, then collect |

## TTS voices

Each voice added later needs a recorded consent from the speaker covering model training and commercial release. Record it here.

| Voice | Speaker consent | Allowed uses |
|---|---|---|
| `af_msa` (Nabra-Saudi, single female voice) | Not documented in the model card; check with the author before adding voices from it | Model weights are Apache-2.0 |

## Open questions

- Does NAMAA hold audio rights for the podcast data? Owner: NAMAA; see the first table row.
- Will we collect our own data? The project maintainer owns the consent process until someone else is named here.
