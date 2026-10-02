"""After-tax value curves of the ETFs held alone and of the six-ETF mix, 2017-04 to 2026-09, for research/mixes.py:  python -m research.curves"""
import numpy as np, pandas as pd
from engine.rules import Rules
from research import panel as P, sim, strategies as st, artifact as A, growth as G
rules=Rules.load('rules')
panel=P.load_panel(end='2026-09-30',assets=P.GROWTH)
i0=int(np.searchsorted(panel.dates,np.datetime64('2017-04-03')));win=P.from_day(panel,i0)
idx=pd.DatetimeIndex(win.dates.astype('datetime64[ns]'))
r=sim.simulate(win,st.s1_static(A.GROWTH_MIX,'year')(win),rules,sim.SimConfig(cap=1.0,**G.NO_GUARD));pd.Series(r.equity,index=idx).to_pickle('research/out/eq_growth.pkl')
r=sim.simulate(win,st.s1_static([1,0,0,0,0,0,0],'year')(win),rules,sim.SimConfig(cap=1.0,**G.NO_GUARD));pd.Series(r.equity,index=idx).to_pickle('research/out/eq_nifty.pkl')
for j,a in enumerate(win.assets):
    w=[0]*7;w[j]=1;r=sim.simulate(win,st.s1_static(w,'year')(win),rules,sim.SimConfig(cap=1.0,**G.NO_GUARD));pd.Series(r.equity,index=idx).to_pickle(f'research/out/eq_{a}.pkl')
