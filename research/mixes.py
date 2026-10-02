"""Mixes of separate accounts (momentum, ETFs), the futures leg and put insurance, from the saved curves:  python -m research.mixes (after research.stockmom runs, research.curves, research.futures, research.options)"""
import numpy as np, pandas as pd
L=lambda n: pd.read_pickle(f'research/out/{n}.pkl')
S={k:L(v) for k,v in dict(mom='eq_mom_0_0',momT='eq_mom_200_0',momTg='eq_mom_200_1',growth='eq_growth',nifty='eq_nifty',gold='eq_GOLDBEES',nasdaq='eq_MON100',midcap='eq_MOM100',junior='eq_JUNIORBEES').items()}
df=pd.concat(S,axis=1).ffill().dropna(); R=df.pct_change().fillna(0)
fut=L('fut_nifty').reindex(df.index).fillna(0)
nb=df.nifty; up=(nb>nb.rolling(200).mean()).shift(1).fillna(False)
yrs=(df.index[-1]-df.index[0]).days/365.25
def stats(r):
    e=(1+r).cumprod();return round(e.iloc[-1]**(1/yrs)-1,3), round((1-e/e.cummax()).max(),3)
def mix(w):   # separate accounts, back to the weights each April (tax of moving money between them not counted)
    out=[];cur=None
    for d,row in R.iterrows():
        if cur is None or (d.month==4 and d.day<=7 and not reb.get(d.year)):
            cur=pd.Series(w,dtype=float);reb[d.year]=True
        x=(cur*row[cur.index]).sum();cur=cur*(1+row[cur.index])/(1+x);out.append(x)
    return pd.Series(out,index=R.index)
def futleg(k,trend=True,tax=0.312):
    g=fut*k*(up if trend else 1)
    # business income: yearly net taxed at slab-ish 31.2%, loss carried
    fy=g.index.to_period('Q-MAR').qyear;out=g.copy();carry=0
    for y in sorted(set(fy)):
        m=fy==y;p=(g[m]).sum()+carry
        t=max(p,0)*tax;carry=min(p,0)
        if t: out[out.index[m][-1]]-=t
    return out
rows=[]
for name in ['nifty','midcap','junior','nasdaq','gold','growth','mom','momT','momTg']: rows.append((name,*stats(R[name])))
for w in [dict(momT=.5,growth=.5),dict(momT=.6,growth=.4),dict(momT=.7,gold=.3),dict(momT=.5,gold=.25,nasdaq=.25),dict(momT=.6,gold=.2,nasdaq=.2),dict(mom=.5,growth=.5)]:
    reb={};rows.append(('+'.join(f'{k}{int(v*100)}' for k,v in w.items()),*stats(mix(w))))
for k in (0.5,1.0):
    for t in (False,True):
        rows.append((f'futures {k}x {"trend" if t else "always"} alone(after tax)',*stats(futleg(k,t))))
reb={};base=mix(dict(momT=.5,growth=.5))
for k in (0.25,0.5):
    rows.append((f'momT50+growth50 + futures {k}x trend',*stats(base+futleg(k,True))))
print(pd.DataFrame(rows,columns=['what','cagr','worst fall']).to_string(index=False))
print('--- put insurance on the mix')
for f,share in (('opt_buy_PE_0.9',0.5),('opt_buy_PE_0.9',1.0),('opt_buy_PE_0.95',0.5)):
    p=pd.read_csv(f'research/out/{f}.csv',parse_dates=['entry','expiry'])
    leg=pd.Series(0.0,index=R.index)
    for _,x in p.iterrows():
        i=R.index.searchsorted(x.expiry)
        if i<len(leg): leg.iloc[i]+=x.pnl*share*(1-0.312*(x.pnl>0))
    for w in [dict(momT=.5,gold=.25,nasdaq=.25),dict(momT=.5,growth=.5)]:
        reb={};print(f,share,w,stats(mix(w)+leg))
