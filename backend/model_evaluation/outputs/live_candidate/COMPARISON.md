# Live-compatible model comparison

Synthetic dataset only. Neither model passed the release gate.

| Split | Metric | Existing offline HGB | Best live-compatible trial |
|---|---|---:|---:|
| time_forward | accuracy | 0.7661 | 0.6162 |
| time_forward | balanced_accuracy | 0.6210 | 0.3529 |
| time_forward | macro_precision | 0.6605 | 0.4371 |
| time_forward | macro_recall | 0.6210 | 0.3529 |
| time_forward | macro_f1 | 0.6330 | 0.3727 |
| time_forward | weighted_f1 | 0.7567 | 0.6317 |
| time_forward | inference ms/sample | not recorded | 0.1476 |
| validation | accuracy | 0.8086 | 0.6705 |
| validation | balanced_accuracy | 0.6635 | 0.4347 |
| validation | macro_precision | 0.6686 | 0.4785 |
| validation | macro_recall | 0.6635 | 0.4347 |
| validation | macro_f1 | 0.6547 | 0.4303 |
| validation | weighted_f1 | 0.7972 | 0.6730 |
| validation | inference ms/sample | not recorded | 0.1358 |
| challenge | accuracy | 0.8458 | 0.6988 |
| challenge | balanced_accuracy | 0.7476 | 0.5157 |
| challenge | macro_precision | 0.8068 | 0.5831 |
| challenge | macro_recall | 0.7476 | 0.5157 |
| challenge | macro_f1 | 0.7582 | 0.5090 |
| challenge | weighted_f1 | 0.8402 | 0.7039 |
| challenge | inference ms/sample | not recorded | 0.1304 |

Candidate selected on validation macro F1 only. Challenge and time-forward are audit results, not tuning inputs.
The original benchmark retains its broader offline feature set and is not live compatible.
Selected candidate training time: 36.86 seconds; baseline training time was not recorded by its evaluator.
See `evaluation.json` for configuration, dataset hash, split manifest, per-class scores, and confusion matrices.
