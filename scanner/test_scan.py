"""Regression fixtures. The first 15 are the v1 fixtures. PROBES are written by the assistant for the four known gaps
(module-wide suppression, multi-column dropna, variable output path, sort check). They are not the external review's six probes."""
from pipeline_scan import scan_source
def rules(s): return sorted({r["rule"] for r in scan_source(s)})
LE="from sklearn.preprocessing import LabelEncoder\n"
T=[
 ("dropna_unscoped","import pandas as pd\ndf=pd.read_csv('a.csv')\ndf=df.dropna()\n",["DROPNA_UNSCOPED"]),
 ("dropna_series","import pandas as pd\nc=df['x'].dropna().unique()\n",[]),
 ("dropna_scoped","import pandas as pd\ndf=pd.read_csv('a.csv')\ndf=df.dropna(subset=['x'])\n",[]),
 ("row_cap_nrows","import pandas as pd\ndf=pd.read_csv('a.csv',nrows=100000)\n",["ROW_CAP"]),
 ("row_cap_sql","q='SELECT * FROM t LIMIT 5000'\n",["ROW_CAP"]),
 ("dead_merge","import pandas as pd\ndef f(a,b):\n    m=a.merge(b,on='k')\n    return a\n",["DEAD_MERGE"]),
 ("live_merge","import pandas as pd\ndef f(a,b):\n    m=a.merge(b,on='k')\n    return m\n",[]),
 ("pos_first","def f(df):\n    return df.groupby('p').first()\n",["POS_SELECT"]),
 ("sorted_first","def f(df):\n    df=df.sort_values('t')\n    return df.groupby('p').first()\n",[]),
 ("enc_per_frame",LE+"def enc(df):\n    for c in ['a']:\n        df[c]=LabelEncoder().fit_transform(df[c])\n    return df\n",["ENC_PER_FRAME"]),
 ("enc_stored",LE+"encoders={}\ndef enc(df):\n    le=LabelEncoder(); encoders['a']=le.fit(df['a']); return encoders['a'].transform(df['a'])\n",[]),
 ("enc_per_frame_var",LE+"def enc(df):\n    out=df.copy()\n    for c in ['a']:\n        le=LabelEncoder()\n        out[c]=le.fit_transform(out[c])\n    return out\n",["ENC_PER_FRAME"]),
 ("const_output","df.to_csv('out.csv')\n",["CONST_OUTPUT"]),
 ("timestamped_output","import datetime\ndf.to_csv('out.csv')\n",[]),
 ("clean","import pandas as pd\ndf=pd.read_csv('a.csv')\nprint(df.shape)\n",[]),
 # PROBES, must flag
 ("PROBE enc: stored encoders in another function must not suppress",LE+"encoders={}\ndef good(df):\n    return encoders['a'].transform(df['a'])\ndef bad(df):\n    df['a']=LabelEncoder().fit_transform(df['a'])\n    return df\n",["ENC_PER_FRAME"]),
 ("PROBE time: timestamp in another function must not suppress output",  "import datetime\ndef stamp():\n    return datetime.datetime.now()\ndef save(df):\n    df.to_csv('out.csv')\n",["CONST_OUTPUT"]),
 ("PROBE dropna: multi-column frame",  "df=df[['a','b']].dropna()\n",["DROPNA_UNSCOPED"]),
 ("PROBE output: constant held in a variable","def save(df):\n    p='out.csv'\n    df.to_csv(p)\n",["CONST_OUTPUT"]),
 ("PROBE sort: sort after the first() does not help","def f(df):\n    g=df.groupby('p').first()\n    return g.sort_values('p')\n",["POS_SELECT"]),
 ("PROBE sort: sort in another function does not help","def a(df):\n    return df.sort_values('t')\ndef b(df):\n    return df.groupby('p').first()\n",["POS_SELECT"]),
 # PROBES, must not flag
 ("PROBE ok: variable column then unique()","def f(df,col):\n    return df[col].dropna().unique()\n",[]),
 ("PROBE ok: variable path with timestamp in same function","import datetime\ndef save(df):\n    p='out_'+datetime.datetime.now().isoformat()+'.csv'\n    df.to_csv(p)\n",[]),
 ("PROBE ok: dropna on columns axis","df=df.dropna(axis=1)\n",[]),
 ("PROBE ok: path is a parameter","def save(df,path):\n    df.to_csv(path)\n",[]),
]
ok=0
for name,src,exp in T:
    got=rules(src); good=got==sorted(exp); ok+=good
    print(("PASS " if good else "FAIL ")+name,"expected",exp,"got",got)
print(f"{ok}/{len(T)} fixtures pass")
