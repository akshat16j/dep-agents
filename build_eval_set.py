"""Emit eval_set.csv. Every `breaking=1` label carries the verbatim source line it came from."""
import csv

# (package, from, to, import_name, tier, [(symbol, breaking, evidence_source_doc, quote)])
# tier: releases | changelog_file | neither  — where the breaking evidence actually lives
ROWS = [
 ("urllib3","1.26.0","2.0.0","","releases",[
   ("urllib3.HTTPResponse.from_httplib",1,"CHANGES.rst + Releases 2.0.0",
    "Removed ``urllib3.HTTPResponse.from_httplib`` (#2648)."),
   ("urllib3.HTTPResponse.getheaders",1,"CHANGES.rst + Releases 2.0.0",
    "Deprecated ``HTTPResponse.getheaders()`` and ``HTTPResponse.getheader()`` which will be removed in urllib3 v2.1.0."),
   ("urllib3.PoolManager",0,"",""),
   ("urllib3.PoolManager.urlopen",0,"",""),
   ("urllib3.HTTPResponse",0,"",""),
 ]),
 ("attrs","20.3.0","22.2.0","","releases",[
   ("attrs.set_run_validators",1,"Releases 21.3.0",
    "Added new context manager `attrs.validators.disabled()` and functions `attrs.validators.(set|get)_disabled()`. They deprecate `attrs.(set|get)_run_validators()`."),
   ("attrs.field",0,"",""),
 ]),
 ("numpy","1.20.0","1.24.0","","releases",[
   ("numpy.polynomial.polybase.PolyBase",1,"Releases 1.24.0",
    "The class `PolyBase` has been removed (deprecated in numpy 1.9.0)."),
   ("numpy.array",0,"",""),
   ("numpy.zeros",0,"",""),
 ]),
 ("flask","1.1.4","2.3.0","","changelog_file",[
   ("flask.safe_join",1,"CHANGES.rst 2.1.0",
    "``safe_join`` is removed, use ``werkzeug.utils.safe_join``"),
   ("flask.json.htmlsafe_dumps",1,"CHANGES.rst 2.3.0",
    "The ``json.htmlsafe_dumps`` and ``htmlsafe_dump`` functions are removed."),
   ("flask.Flask",0,"",""),
   ("flask.jsonify",0,"",""),
 ]),
 ("jinja2","2.11.0","3.1.0","","changelog_file",[
   ("jinja2.contextfunction",1,"CHANGES.rst 3.0.0",
    "``contextfilter`` and ``contextfunction`` are replaced by"),
   ("jinja2.unicode_urlencode",1,"CHANGES.rst 3.0.0",
    "``unicode_urlencode`` is renamed to ``url_quote``."),
   ("jinja2.Environment",0,"",""),
   ("jinja2.Template",0,"",""),
 ]),
 ("click","7.1.2","8.1.0","","changelog_file",[
   ("click.get_terminal_size",1,"CHANGES.md 8.1.0",
    "`get_terminal_size` is removed, use"),
   ("click.get_os_args",1,"CHANGES.md 8.1.0",
    "`get_os_args` is removed, use `sys.argv[1:]` instead."),
   ("click.echo",0,"",""),
   ("click.option",0,"",""),
 ]),
 ("markupsafe","1.1.1","2.1.0","","changelog_file",[
   ("markupsafe.soft_unicode",1,"CHANGES.rst 2.1.0",
    "Remove ``soft_unicode``, which was previously deprecated. Use"),
   ("markupsafe.Markup",0,"",""),
   ("markupsafe.escape",0,"",""),
 ]),
 ("werkzeug","1.0.1","2.3.0","","changelog_file",[
   ("werkzeug.wsgi.make_line_iter",1,"CHANGES.rst 2.3.0",
    "Deprecate ``werkzeug.wsgi.make_line_iter`` and ``make_chunk_iter``."),
   ("werkzeug.utils.safe_join",0,"",""),
   ("werkzeug.Response",0,"",""),
 ]),
 # tier 3: breaking change is real but documented OUTSIDE Releases and the root changelog
 ("pydantic","1.10.0","2.0.0","","neither",[
   ("pydantic.BaseModel.dict",1,"docs/migration.md (NOT in Releases or HISTORY.md)",
    "| `dict()` | `model_dump()` |"),
   ("pydantic.BaseModel",0,"",""),
 ]),
 ("pandas","1.5.0","2.0.0","","neither",[
   ("pandas.DataFrame.append",1,"doc/source/whatsnew/v2.0.0.rst (NOT in Releases; no root changelog)",
    "Removed deprecated :meth:`Series.append`, :meth:`DataFrame.append`, use :func:`concat` instead"),
   ("pandas.DataFrame",0,"",""),
   ("pandas.read_csv",0,"",""),
 ]),
 # true negatives: no removals/deprecations documented for these symbols
 ("requests","2.28.0","2.31.0","","none-documented",[
   ("requests.get",0,"",""),
   ("requests.post",0,"",""),
   ("requests.Session",0,"",""),
 ]),
 ("httpx","0.23.0","0.24.1","","releases",[
   ("httpx.get",0,"",""),
   ("httpx.Client",0,"",""),
   ("httpx.AsyncClient",0,"",""),
 ]),
 ("scikit-learn","1.0.2","1.3.0","sklearn","none-documented",[
   ("sklearn.linear_model.LogisticRegression",0,"",""),
   ("sklearn.metrics.accuracy_score",0,"",""),
 ]),
]

COLS = ["package","from_version","to_version","import_name","source_tier","symbol",
        "gt_breaking","gt_severity","gt_evidence_doc","gt_evidence_quote",
        "pred_breaking","pred_grounded","pred_evidence_source","pred_patch","model","run_id"]

SEVERITY = {'urllib3.HTTPResponse.from_httplib': 'removed', 'urllib3.HTTPResponse.getheaders': 'deprecated', 'attrs.set_run_validators': 'deprecated', 'numpy.polynomial.polybase.PolyBase': 'removed', 'flask.safe_join': 'removed', 'flask.json.htmlsafe_dumps': 'removed', 'jinja2.contextfunction': 'removed', 'jinja2.unicode_urlencode': 'removed', 'click.get_terminal_size': 'removed', 'click.get_os_args': 'removed', 'markupsafe.soft_unicode': 'removed', 'werkzeug.wsgi.make_line_iter': 'deprecated', 'pydantic.BaseModel.dict': 'removed', 'pandas.DataFrame.append': 'removed'}


if __name__ == "__main__":
    with open("eval_set.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for pkg, lo, hi, imp, tier, syms in ROWS:
            for sym, br, doc, quote in syms:
                w.writerow([pkg, lo, hi, imp, tier, sym, br, SEVERITY.get(sym, "none"), doc, quote,
                            "", "", "", "", "", ""])
    n = sum(len(r[5]) for r in ROWS)
    b = sum(1 for r in ROWS for s in r[5] if s[1])
    print(f"{len(ROWS)} upgrades | {n} usages | {b} breaking ({b/n:.0%}) | {n-b} non-breaking")
    from collections import Counter
    print("tiers:", dict(Counter(r[4] for r in ROWS)))
