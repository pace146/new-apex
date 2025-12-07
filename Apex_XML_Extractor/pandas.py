+import builtins
+import csv
+import math
+from collections import Counter, defaultdict
+
+
+def is_nan(val):
+    try:
+        return val != val or math.isnan(float(val))
+    except Exception:
+        return val is None
+
+
+def to_numeric(series, errors="raise"):
+    data = []
+    for v in series:
+        try:
+            data.append(float(v))
+        except Exception:
+            if errors == "coerce":
+                data.append(math.nan)
+            else:
+                raise
+    return Series(data)
+
+
+class Series(list):
+    def __init__(self, data=None, name=None):
+        super().__init__(data or [])
+        self.name = name
+        self.iloc = _SeriesIndexer(self)
+
+    @property
+    def values(self):
+        return list(self)
+
+    def astype(self, dtype):
+        res = []
+        for v in self:
+            try:
+                res.append(dtype(v))
+            except Exception:
+                res.append(math.nan)
+        return Series(res, name=self.name)
+
+    def isna(self):
+        return Series([is_nan(v) for v in self])
+
+    def fillna(self, value):
+        return Series([value if is_nan(v) else v for v in self])
+
+    def clip(self, lower=None, upper=None):
+        res = []
+        for v in self:
+            val = v
+            if lower is not None and (val < lower or is_nan(val)):
+                val = lower
+            if upper is not None and val > upper:
+                val = upper
+            res.append(val)
+        return Series(res, name=self.name)
+
+    def rank(self, method="average", ascending=True):
+        # Only method="min" is used in this codebase
+        sorted_vals = sorted([(v, i) for i, v in enumerate(self)], reverse=not ascending)
+        ranks = [0] * len(self)
+        current_rank = 1
+        i = 0
+        while i < len(sorted_vals):
+            j = i
+            while j < len(sorted_vals) and sorted_vals[j][0] == sorted_vals[i][0]:
+                j += 1
+            rank_val = current_rank if method == "min" else (current_rank + j - 1) / 2
+            for k in range(i, j):
+                ranks[sorted_vals[k][1]] = rank_val
+            current_rank = j + 1
+            i = j
+        return Series(ranks)
+
+    def value_counts(self, normalize=False):
+        counter = Counter(self)
+        if normalize:
+            total = sum(counter.values()) or 1
+            for k in counter:
+                counter[k] /= total
+        return counter
+
+    def sum(self):
+        total = 0
+        for v in self:
+            try:
+                total += v
+            except Exception:
+                continue
+        return total
+
+    def std(self, ddof=0):
+        vals = [float(v) for v in self if not is_nan(v)]
+        n = len(vals)
+        if n == 0:
+            return math.nan
+        mean_val = sum(vals) / n
+        var = sum((v - mean_val) ** 2 for v in vals) / max(1, n - ddof)
+        return math.sqrt(var)
+
+    def max(self):
+        try:
+            return builtins.max(self)
+        except Exception:
+            return None
+
+    def isin(self, options):
+        return Series([v in options for v in self])
+
+    # arithmetic operations
+    def _binary_op(self, other, op):
+        if isinstance(other, Series):
+            length = max(len(self), len(other))
+            res = []
+            for i in range(length):
+                a = self[i] if i < len(self) else math.nan
+                b = other[i] if i < len(other) else math.nan
+                try:
+                    res.append(op(a, b))
+                except Exception:
+                    res.append(math.nan)
+            return Series(res)
+        else:
+            res = []
+            for a in self:
+                try:
+                    res.append(op(a, other))
+                except Exception:
+                    res.append(math.nan)
+            return Series(res)
+
+    def __add__(self, other):
+        return self._binary_op(other, lambda a, b: a + b)
+
+    def __sub__(self, other):
+        return self._binary_op(other, lambda a, b: a - b)
+
+    def __mul__(self, other):
+        return self._binary_op(other, lambda a, b: a * b)
+
+    def __truediv__(self, other):
+        return self._binary_op(other, lambda a, b: a / b)
+
+    def __radd__(self, other):
+        return self.__add__(other)
+
+    def __rsub__(self, other):
+        return self._binary_op(other, lambda a, b: other - a)
+
+    def __rmul__(self, other):
+        return self.__mul__(other)
+
+    def __ge__(self, other):
+        return self._binary_op(other, lambda a, b: a >= b)
+
+    def __le__(self, other):
+        return self._binary_op(other, lambda a, b: a <= b)
+
+    def __gt__(self, other):
+        return self._binary_op(other, lambda a, b: a > b)
+
+    def __lt__(self, other):
+        return self._binary_op(other, lambda a, b: a < b)
+
+    def __and__(self, other):
+        return self._binary_op(other, lambda a, b: bool(a) and bool(b))
+
+    def __or__(self, other):
+        return self._binary_op(other, lambda a, b: bool(a) or bool(b))
+
+    def __invert__(self):
+        return Series([not bool(v) for v in self])
+
+    def __eq__(self, other):
+        return self._binary_op(other, lambda a, b: a == b)
+
+    def __ne__(self, other):
+        return self._binary_op(other, lambda a, b: a != b)
+
+    def tolist(self):
+        return list(self)
+
+    def unique(self):
+        seen = []
+        for v in self:
+            if v not in seen:
+                seen.append(v)
+        return Series(seen)
+
+
+class _SeriesIndexer:
+    def __init__(self, series: 'Series'):
+        self.series = series
+
+    def __getitem__(self, idx):
+        return self.series[idx]
+
+
+class _LocIndexer:
+    def __init__(self, df: 'DataFrame'):
+        self.df = df
+
+    def __getitem__(self, key):
+        if isinstance(key, tuple) and len(key) == 2:
+            rows, cols = key
+            sub = self.df[rows] if isinstance(rows, Series) else self.df
+            if isinstance(cols, list):
+                return sub[cols]
+            return Series(sub[cols])
+        return self.df[key]
+
+
+class DataFrame:
+    def __init__(self, data=None, columns=None):
+        self.rows = []
+        if isinstance(data, list):
+            if data and isinstance(data[0], dict):
+                self.rows = [dict(row) for row in data]
+                if columns is None and data:
+                    columns = list(data[0].keys())
+        self.columns = columns or []
+        self.loc = _LocIndexer(self)
+
+    def __len__(self):
+        return len(self.rows)
+
+    @property
+    def empty(self):
+        return len(self.rows) == 0
+
+    def __getitem__(self, key):
+        if isinstance(key, Series):
+            mask = [bool(v) for v in key]
+            filtered = [row for row, keep in zip(self.rows, mask) if keep]
+            return DataFrame(filtered, columns=self.columns)
+        if isinstance(key, list):
+            return DataFrame([{k: row.get(k) for k in key} for row in self.rows], columns=key)
+        return Series([row.get(key) for row in self.rows], name=key)
+
+    def __setitem__(self, key, value):
+        if isinstance(value, Series):
+            vals = list(value)
+        elif isinstance(value, list):
+            vals = value
+        else:
+            vals = [value for _ in range(len(self.rows))]
+        if key not in self.columns:
+            self.columns.append(key)
+        for i, row in enumerate(self.rows):
+            row[key] = vals[i] if i < len(vals) else None
+
+    def iterrows(self):
+        for idx, row in enumerate(self.rows):
+            yield idx, row
+
+    def copy(self):
+        return DataFrame(self.rows, columns=list(self.columns))
+
+    def to_csv(self, path, index=False, encoding=None):
+        fieldnames = self.columns
+        with open(path, "w", newline="", encoding=encoding or "utf-8") as f:
+            writer = csv.DictWriter(f, fieldnames=fieldnames)
+            writer.writeheader()
+            for row in self.rows:
+                writer.writerow({col: row.get(col, "") for col in fieldnames})
+
+    def to_excel(self, *args, **kwargs):
+        raise NotImplementedError("Excel export not supported in lightweight pandas stub")
+
+    def merge(self, other, on, how="left"):
+        return merge(self, other, on=on, how=how)
+
+    def groupby(self, key, **kwargs):
+        groups = defaultdict(list)
+        for row in self.rows:
+            groups[row.get(key)].append(row)
+        return GroupBy({k: DataFrame(v, columns=self.columns) for k, v in groups.items()})
+
+    def sort_values(self, by, ascending=True):
+        if isinstance(by, list):
+            by = by[0]
+        sorted_rows = sorted(self.rows, key=lambda r: (r.get(by) is None, r.get(by)))
+        if not ascending:
+            sorted_rows.reverse()
+        return DataFrame(sorted_rows, columns=self.columns)
+
+    def reset_index(self, drop=False):
+        return DataFrame(self.rows, columns=self.columns)
+
+    def nsmallest(self, n, column):
+        sorted_rows = sorted(self.rows, key=lambda r: (r.get(column) is None, r.get(column)))
+        return DataFrame(sorted_rows[:n], columns=self.columns)
+
+    def astype(self, dtype):
+        for col in self.columns:
+            self[col] = Series(self[col]).astype(dtype)
+        return self
+
+    def drop(self, columns=None):
+        cols = set(columns or [])
+        new_rows = [{k: v for k, v in row.items() if k not in cols} for row in self.rows]
+        new_cols = [c for c in self.columns if c not in cols]
+        return DataFrame(new_rows, columns=new_cols)
+
+
+class GroupBy:
+    def __init__(self, groups):
+        self.groups = groups
+
+    def __iter__(self):
+        for k, df in self.groups.items():
+            yield k, df
+
+    def __getitem__(self, item):
+        # return groupby over selected column
+        new_groups = {}
+        for k, df in self.groups.items():
+            new_groups[k] = DataFrame([{item: row.get(item)} for row in df.rows], columns=[item])
+        return GroupBy(new_groups)
+
+    def max(self):
+        results = {}
+        for k, df in self.groups.items():
+            col = df.columns[0] if df.columns else None
+            if col:
+                results[k] = Series(df[col]).max()
+        return Series([results[k] for k in results], name="max").astype(float)
+
+    def apply(self, func):
+        rows = []
+        for _, df in self.groups.items():
+            res = func(df)
+            if isinstance(res, DataFrame):
+                rows.extend(res.rows)
+            elif isinstance(res, Series):
+                rows.append({res.name: list(res)})
+        return DataFrame(rows, columns=self.groups[next(iter(self.groups))].columns if self.groups else [])
+
+
+def read_csv(path, encoding=None):
+    with open(path, newline="", encoding=encoding or "utf-8") as f:
+        reader = csv.DictReader(f)
+        rows = [row for row in reader]
+        return DataFrame(rows, columns=reader.fieldnames)
+
+
+def merge(left: DataFrame, right: DataFrame, on, how="left"):
+    if how != "left":
+        raise NotImplementedError("Only left join supported in stub")
+    keys = on if isinstance(on, (list, tuple)) else [on]
+
+    def make_key(row):
+        return tuple(row.get(k) for k in keys)
+
+    rows = []
+    right_map = defaultdict(list)
+    for r in right.rows:
+        right_map[make_key(r)].append(r)
+    for l in left.rows:
+        matches = right_map.get(make_key(l), [{}])
+        for m in matches:
+            combined = dict(l)
+            for k, v in m.items():
+                if k in keys:
+                    continue
+                combined[k] = v
+            rows.append(combined)
+    columns = list({*left.columns, *[c for c in right.columns if c not in keys]})
+    return DataFrame(rows, columns=columns)
+
+
+def DataFrame_from_records(records):
+    return DataFrame(records, columns=list(records[0].keys()) if records else [])
+
+
+__all__ = [
+    "DataFrame",
+    "Series",
+    "read_csv",
+    "to_numeric",
+    "merge",
+    "DataFrame_from_records",
+]
 
EOF
)
