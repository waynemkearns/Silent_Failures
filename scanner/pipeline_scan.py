"""
Prototype static scanner for CODE-VISIBLE candidate patterns in Python/Pandas pipelines. PROTOTYPE, not validated.
It flags candidates. A flag is suspicious code, never a verified defect. Output must be judged in context.
v2 (12 Oct 2026): every suppression is now scoped to the function that holds the call, not the whole module.
Rules:
 ENC_PER_FRAME   LabelEncoder fitted with fit_transform and no stored-encoder reuse in the same function (candidate for inconsistent codes across frames).
 DROPNA_UNSCOPED .dropna() on a DataFrame with no subset (P6). Skips single-column Series such as df['x'].dropna() and axis=1 drops.
                 df[['a','b']].dropna() is flagged because it drops rows of a frame.
 ROW_CAP         read_csv/read_* with nrows=..., or a string containing SQL LIMIT (P2).
 DEAD_MERGE      x = <expr>.merge(...) where x is never read again in the module (P3).
 POS_SELECT      .first() / .drop_duplicates() / .iloc[0] with no sort_values/sort_index EARLIER in the same function (P1).
 CONST_OUTPUT    to_csv / to_parquet / to_pickle with a constant path (a string, a constant f-string, or a name bound to a constant string)
                 and no timestamp/hash use in the same function (P7).
"""
import ast, sys, json
from pathlib import Path

SERIES_METHODS=("unique","nunique","tolist","to_list","values","mean","sum","median","std","min","max","count")
TIME_WORDS=("strftime","datetime","timestamp","uuid","sha256","hashlib","time.time")

def scan_source(src, fname="<src>"):
    try: tree=ast.parse(src)
    except SyntaxError as e: return [{"file":fname,"rule":"PARSE_ERROR","line":e.lineno or 0}]
    out=[]; add=lambda rule,node: out.append({"file":fname,"rule":rule,"line":node.lineno})
    parent={}
    for p in ast.walk(tree):
        for c in ast.iter_child_nodes(p): parent[c]=p
    def scope_of(node):
        while node in parent:
            node=parent[node]
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)): return node
        return tree
    def own_nodes(scope):
        """Nodes belonging to this scope, not to a nested function."""
        res=[]; stack=list(ast.iter_child_nodes(scope))
        while stack:
            n=stack.pop(); res.append(n)
            if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)): stack.extend(ast.iter_child_nodes(n))
            else: res.append(n)
        return res
    cache={}
    def info(scope):
        if scope in cache: return cache[scope]
        nodes=own_nodes(scope); seg=ast.get_source_segment(src,scope) or src if scope is not tree else "\n".join(
            ast.get_source_segment(src,n) or "" for n in tree.body if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)))
        params=[a.arg for a in (scope.args.args+scope.args.kwonlyargs)] if scope is not tree else []
        stored=any(isinstance(n,ast.Subscript) and isinstance(n.value,ast.Name) and "encoder" in n.value.id.lower() for n in nodes) \
            or any("encoder" in p.lower() for p in params) or ("fit_encoders" in seg)
        uses_time=any(k in seg for k in TIME_WORDS)
        sorts=[c.lineno for c in nodes if isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and c.func.attr in ("sort_values","sort_index")]
        consts={}
        for n in nodes:
            if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
                v=n.value
                if isinstance(v,ast.Constant) and isinstance(v.value,str): consts[n.targets[0].id]=v.value
        cache[scope]=dict(stored=stored,uses_time=uses_time,sorts=sorts,consts=consts); return cache[scope]
    module_consts=info(tree)["consts"]
    loads={n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}
    le_names={t.id for n in ast.walk(tree) if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call)
              and getattr(n.value.func,"id",getattr(n.value.func,"attr",""))=="LabelEncoder"
              for t in n.targets if isinstance(t,ast.Name)}
    def const_path(arg,scope):
        if isinstance(arg,ast.Constant) and isinstance(arg.value,str): return True
        if isinstance(arg,ast.JoinedStr) and not any(isinstance(v,ast.FormattedValue) for v in arg.values): return True
        if isinstance(arg,ast.Name): return arg.id in info(scope)["consts"] or (scope is not tree and arg.id in module_consts and arg.id not in [a.arg for a in scope.args.args])
        return False
    for n in ast.walk(tree):
        sc=scope_of(n)
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute):
            a=n.func.attr
            if a=="dropna" and not n.args and not any(k.arg=="subset" for k in n.keywords):
                axis=[k.value.value for k in n.keywords if k.arg=="axis" and isinstance(k.value,ast.Constant)]
                v=n.func.value; series=isinstance(v,ast.Subscript) and isinstance(v.slice,ast.Constant)
                par=parent.get(n)   # df[col].dropna().unique() and similar chains work on a Series
                if isinstance(par,ast.Attribute) and par.attr in SERIES_METHODS: series=True
                if not series and not any(x in (1,"columns") for x in axis): add("DROPNA_UNSCOPED",n)
            if a.startswith("read_") and any(k.arg=="nrows" for k in n.keywords): add("ROW_CAP",n)
            if a=="fit_transform":
                v=n.func.value
                is_le=(isinstance(v,ast.Call) and getattr(v.func,"id",getattr(v.func,"attr",""))=="LabelEncoder") or (isinstance(v,ast.Name) and v.id in le_names)
                if is_le and not info(sc)["stored"]: add("ENC_PER_FRAME",n)
            if a in ("first","drop_duplicates") and not any(l<n.lineno for l in info(sc)["sorts"]): add("POS_SELECT",n)
            if a in ("to_csv","to_parquet","to_pickle") and n.args and const_path(n.args[0],sc) and not info(sc)["uses_time"]: add("CONST_OUTPUT",n)
        if isinstance(n,ast.Subscript) and isinstance(n.value,ast.Attribute) and n.value.attr=="iloc":
            s=n.slice
            if isinstance(s,ast.Constant) and s.value==0 and not any(l<n.lineno for l in info(sc)["sorts"]): add("POS_SELECT",n)
        if isinstance(n,ast.Constant) and isinstance(n.value,str) and " limit " in (" "+n.value.lower()+" ") and "select" in n.value.lower(): add("ROW_CAP",n)
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and isinstance(n.value,ast.Call):
            f=n.value.func
            if (isinstance(f,ast.Attribute) and f.attr=="merge") and n.targets[0].id not in loads: add("DEAD_MERGE",n)
    return sorted(out,key=lambda r:(r["line"],r["rule"]))

def scan_file(p): return scan_source(Path(p).read_text(errors="replace"),str(p))
if __name__=="__main__":
    res=[]
    for p in sys.argv[1:]: res+=scan_file(p)
    print(json.dumps(res,indent=1))
