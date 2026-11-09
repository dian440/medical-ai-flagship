# Cross-dataset evaluation of chest radiograph classifiers: prevalence, calibration, and the noise baseline

**Repository accompanying a manuscript submitted to *BMC Medical Imaging*.**

> Class prevalence changes which chest radiograph dataset looks better:
> a cross-dataset audit of four publicly released classifiers

---

## What this repository contains

An audit of four publicly released chest radiograph classifiers (DenseNet-121, identical
architecture, differing only in pretraining source) evaluated on three independently
collected chest radiograph datasets (NIH ChestX-ray14, Kermany, VinDr-CXR), each reduced to
one identically defined binary task.

The central finding is methodological rather than architectural. Resampling all three
evaluation cohorts to a common class prevalence contracted the calibration spread in seven of
eight model–label combinations and reversed the calibration ranking in all eight. More
consequentially, the paper establishes the **reference quantity against which such a reversal
must be judged**: under a null in which the three datasets are of *identical* calibration and
differ only in resampling noise, prior matching alone reorders them in **82.3–84.4%** of
replicates. A cross-dataset calibration comparison that omits such a baseline cannot be
interpreted.

The repository also reports and corrects an error in circulating implementations of the
variance estimator of DeLong's test, which overstates the standard error most severely where
class imbalance is greatest.

---

## Repository layout

```
code/                              Analysis and figure-generation code
  multi_model_metrics.py           Four-model evaluation; AUC, ECE, DeLong comparison
  noise_baseline.py                Observed ranking change vs. the three null constructions
  prevalence_matched_null_baseline.py
                                   PMNB: the reusable, metric-agnostic baseline procedure
  validate_pmnb.py                Independent re-implementation check (reproduces all 8 groups)
  adjudicate_delong.py             Three-way adjudication of the DeLong variance estimator
  diagnose_delong_variance.py     Localises the variance-formula and midrank-assembly defects
  verify_delong_independent.py     Independent O(m×n) implementation of the test
  prior_matched / label_sensitivity / operating_points / dca / retrain_baseline
                                   The remaining analyses reported in the paper
  figure0_graphical_abstract.py   Graphical abstract (1200 × 600 px)
  figure1_flowchart.py             Figure 1 — study flow
  figure2_calibration.py           Figure 2 — reliability curves
  figure3_decision_curve.py        Figure 3 — decision curves
  figure4_noise_baseline.py        Figure 4 — observed change vs. noise baselines
  make_tables.py                   Generates all five tables from results/*.json
  verify_*.py, reviewer_gate.py, final_audit.py
                                   Verification: every reported number is re-derived from the
                                   authoritative JSON and cross-checked

results/                           Authoritative analysis output
  multi_model_metrics.json         ** Primary metrics: AUC, ECE, DeLong Δ/SE/CI/p
  multi_model_prior_matched.json   Spread contraction and ranking reversal under prior matching
  noise_baseline.json              Observed change rate against each null construction
  label_sensitivity_noise_baseline.json
                                   Strict VinDr-CXR label definition
  multi_model_dca.json             Decision-curve analysis
  retrain_baseline.json            Frozen-backbone retraining baseline
  operating_points.json            F1 / sensitivity / specificity at the F1-maximising threshold
  multi_model_predictions.csv      Per-image predicted scores for all 37,396 evaluated images
  delong_adjudication.json         Three-way adjudication of the DeLong estimator
  flip_criteria_validation.json    Permutation nulls for the reversal-direction statistic

figures/                           All figures, 300 dpi PNG plus vector PDF
  Figure0_graphical_abstract       1200 × 600 px
  Figure1_flowchart … Figure4_noise_baseline
  FigureS1_calibration_all_models

docs/                              Manuscript drafts (English + Chinese counterpart)
  论文Abstract草稿_v1.md           论文Introduction草稿_v1.md
  论文Methods草稿_v1.md            论文Results草稿_v1.md
  论文Discussion正文_v1.md         论文Tables草稿_v1.md
  参考文献总表_v1.md               Reference list, every entry independently verified

tools/pmnb/                        The PMNB procedure as a standalone, documented package
```

---

## Reproducing the analyses

Requires Python 3.12+ with `numpy`, `scipy`, `pandas`, `scikit-learn`, and `matplotlib`.
Model weights and datasets are not redistributed here; they are obtained through
`torchxrayvision` and the original dataset distributions.

```bash
# Re-derive every reported number from the analysis output, then cross-check the drafts
python code/verify_results_draft.py     # Results: every numeric claim traced to its JSON field
python code/verify_figures.py           # Figures: every annotated value traced to its JSON field
python code/verify_tables.py            # Tables: every cell traced to its JSON field
python code/verify_discussion.py        # Discussion: numbers, sentence length, citation coverage
python code/validate_pmnb.py            # The reusable tool reproduces all 8 published groups

# Regenerate the tables and figures
python code/make_tables.py
python code/figure0_graphical_abstract.py
python code/figure1_flowchart.py
python code/figure2_calibration.py
python code/figure3_decision_curve.py
python code/figure4_noise_baseline.py

# Full submission-readiness audit (84 checks against the eight principal causes of rejection)
python code/final_audit.py
```

The verification scripts exit non-zero if any reported number cannot be re-derived from
`results/*.json`, so they are usable as continuous-integration checks.

---

## Using the prevalence-matched null baseline

The baseline procedure is packaged separately under `tools/pmnb/` so that it can be applied to
comparisons other than the ones reported here.

```python
from prevalence_matched_null_baseline import pmnb

result = pmnb(
    datasets={
        "siteA": {"y": y_a, "score": s_a},
        "siteB": {"y": y_b, "score": s_b},
        "siteC": {"y": y_c, "score": s_c},
    },
    metric="ece",          # "ece" | "auc" | "brier"
    n_reps=500,
    seed=20261104,
)

print(result.baseline_rate)   # rate at which the ranking changes under the null
print(result.observed_rate)   # rate observed in the real data
print(result.exceeds)         # whether the observed change exceeds the baseline
print(result.report())
```

The implementation in `tools/pmnb/` was written independently of the analysis scripts that
produced the paper's results; applying it to the same data reproduces every published change
rate and baseline rate (see `code/validate_pmnb.py`).

---

## Data availability

All datasets analysed are publicly available and were used under their original terms of use:

- **NIH ChestX-ray14** — NIH Clinical Center provides the dataset via the
  [NIH ChestX-ray14 dataset page](https://nihcc.app.box.com/v/ChestXray-NIHCC);
  the paper's labels derive from the published NLP-annotated release.
- **Kermany chest X-ray** — paediatric chest radiographs distributed in curated binary folders
  (NORMAL / PNEUMONIA) as described by Kermany et al. (Cell, 2018).
- **VinDr-CXR** — Vietnamese chest radiographs with radiologist annotations, released as
  VinDr-CXR (Nguyen et al., *Scientific Data*, 2022).

Model weights are obtained from the `torchxrayvision` package (Cohen et al., MIDL 2022), which
distributes DenseNet-121 classifiers pretrained on NIH ChestX-ray14, CheXpert, and two MIMIC-CXR
label variants.

Intermediate feature caches and per-model inference caches are excluded from the repository by
`.gitignore`; they are regenerated by the inference scripts.

---

## Ethics

The study is a retrospective evaluation of publicly released models on publicly available
images. It involves no patient contact, no prospective enrolment, and no intervention;
institutional review board approval was therefore not required under the policies of the
authors' institution. The authors declare no competing interests.

---

## Citation

If you use the prevalence-matched null baseline, the corrected DeLong variance estimator, or
the verification scripts in this repository, please cite the corresponding paper. A
methodological description of the baseline is given in the section that introduces it.

---

## Licence

MIT — see `LICENSE`.

The source datasets and model weights are **not** covered by this licence; they remain subject
to their original terms of use and, in the case of the NIH dataset, to the NIH data
distribution agreement.
