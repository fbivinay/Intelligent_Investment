"""The committed list of deep-model configurations, written before any result of them was seen (plan 3B, task 8). Every one is a trial in the ledger.

Three architectures, two window lengths, two costs per unit of turnover in the loss (5 and 20 basis points), three seeds averaged inside each: 12 trials. The model list in the
spec also names LSTM and a transformer; they are implemented and tested but not in the committed list, so they add nothing to the count.
"""
SEEDS = (0, 1, 2)
VAL_DAYS = 126                 # validation days at the end of each training window
MIN_SAMPLES = 300              # fewer training days than this and the weights stay equal
ARCHS = ("gru", "tcn", "mlp")
SEQ_LENS = (63, 126)
COSTS = (0.0005, 0.002)


def committed() -> list[dict]:
    return [{"name": f"{a}-L{n}-c{round(c * 1e4)}", "arch": a, "seq_len": n, "cost": c} for a in ARCHS for n in SEQ_LENS for c in COSTS]
