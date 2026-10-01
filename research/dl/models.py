"""Position models: a window of normalised features in, five logits out (the four ETFs and the cash leg), softmax to weights.

The last layer starts at zero, so an untrained model holds equal weights: the prior is the 1/N portfolio, and training moves away from it only as far as the data pushes. Every
window ends on the day the weights are decided, so nothing here can see later days (the transformer attends over the window only, all of it past).
"""
import torch
from torch import nn

ARCHS = ("mlp", "gru", "lstm", "tcn", "transformer")


def _head(n_in: int) -> nn.Linear:
    h = nn.Linear(n_in, 5)
    nn.init.zeros_(h.weight)
    nn.init.zeros_(h.bias)
    return h


class MLP(nn.Module):
    """Today's features, their last-21-day mean and the whole window's mean, through two small layers."""
    def __init__(self, n_features: int, hidden: int):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(3 * n_features, hidden), nn.Tanh(), nn.Linear(hidden, hidden), nn.Tanh())
        self.head = _head(hidden)

    def forward(self, x):
        k = min(21, x.shape[1])
        return self.head(self.net(torch.cat([x[:, -1], x[:, -k:].mean(1), x.mean(1)], dim=-1)))


class Recurrent(nn.Module):
    def __init__(self, cell, n_features: int, hidden: int):
        super().__init__()
        self.rnn = cell(n_features, hidden, batch_first=True)
        self.head = _head(hidden)

    def forward(self, x):
        return self.head(self.rnn(x)[0][:, -1])


class TCN(nn.Module):
    """Causal dilated convolutions with residual connections; the last time step feeds the head."""
    def __init__(self, n_features: int, hidden: int, dilations=(1, 2, 4, 8), kernel: int = 3):
        super().__init__()
        self.inp = nn.Conv1d(n_features, hidden, 1)
        self.pads = [(kernel - 1) * d for d in dilations]
        self.convs = nn.ModuleList([nn.Conv1d(hidden, hidden, kernel, dilation=d, padding=p) for d, p in zip(dilations, self.pads)])
        self.head = _head(hidden)

    def forward(self, x):
        h = self.inp(x.transpose(1, 2))
        for conv, pad in zip(self.convs, self.pads):
            h = h + torch.relu(conv(h)[:, :, :-pad])                      # drop the right-hand padding: position t sees only positions up to t
        return self.head(h[:, :, -1])


class Transformer(nn.Module):
    def __init__(self, n_features: int, seq_len: int, hidden: int, heads: int = 2):
        super().__init__()
        self.inp = nn.Linear(n_features, hidden)
        self.pos = nn.Parameter(torch.zeros(seq_len, hidden))
        self.enc = nn.TransformerEncoder(nn.TransformerEncoderLayer(hidden, heads, dim_feedforward=2 * hidden, dropout=0.0, batch_first=True), 1)
        self.head = _head(hidden)

    def forward(self, x):
        return self.head(self.enc(self.inp(x) + self.pos[-x.shape[1]:])[:, -1])


def make_model(arch: str, n_features: int, seq_len: int, hidden: int = 16) -> nn.Module:
    if arch == "mlp":
        return MLP(n_features, hidden)
    if arch == "gru":
        return Recurrent(nn.GRU, n_features, hidden)
    if arch == "lstm":
        return Recurrent(nn.LSTM, n_features, hidden)
    if arch == "tcn":
        return TCN(n_features, hidden)
    if arch == "transformer":
        return Transformer(n_features, seq_len, hidden)
    raise ValueError(f"unknown architecture {arch!r}; the choices are {ARCHS}")


def weights(model: nn.Module, x: torch.Tensor) -> torch.Tensor:
    return torch.softmax(model(x), dim=-1)
