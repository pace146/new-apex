+import builtins
+import math
+import random as _random
+
+nan = math.nan
+
+
+def array(values, dtype=float):
+    res = []
+    for v in values:
+        try:
+            res.append(dtype(v))
+        except Exception:
+            res.append(math.nan)
+    return res
+
+
+def nanmedian(arr):
+    vals = [v for v in arr if v == v and math.isfinite(v)]
+    if not vals:
+        return math.nan
+    vals.sort()
+    n = len(vals)
+    mid = n // 2
+    if n % 2:
+        return vals[mid]
+    return (vals[mid - 1] + vals[mid]) / 2.0
+
+
+def nanmean(arr):
+    vals = [v for v in arr if v == v and math.isfinite(v)]
+    if not vals:
+        return math.nan
+    return sum(vals) / len(vals)
+
+
+def abs(val):
+    try:
+        return math.fabs(val)
+    except Exception:
+        return val
+
+
+def isfinite(val):
+    try:
+        return math.isfinite(val)
+    except Exception:
+        return False
+
+
+def clip(arr, a_min=None, a_max=None):
+    if isinstance(arr, (int, float)):
+        val = arr
+        if a_min is not None:
+            val = max(a_min, val)
+        if a_max is not None:
+            val = min(a_max, val)
+        return val
+    res = []
+    for v in arr:
+        val = v
+        if a_min is not None and val < a_min:
+            val = a_min
+        if a_max is not None and val > a_max:
+            val = a_max
+        res.append(val)
+    return res
+
+
+def mean(arr):
+    vals = [v for v in arr if v == v and math.isfinite(v)]
+    if not vals:
+        return math.nan
+    return sum(vals) / len(vals)
+
+
+def min(arr):
+    try:
+        return builtins.min(arr)
+    except Exception:
+        return math.nan
+
+
+def max(arr):
+    try:
+        return builtins.max(arr)
+    except Exception:
+        return math.nan
+
+
+def zeros(n, dtype=float):
+    return [dtype(0) for _ in range(n)]
+
+
+def where(condition, x, y):
+    if isinstance(condition, list):
+        out = []
+        for i, flag in enumerate(condition):
+            xv = x[i] if isinstance(x, list) else x
+            yv = y[i] if isinstance(y, list) else y
+            out.append(xv if flag else yv)
+        return out
+    return x if condition else y
+
+
+class RandomModule:
+    @staticmethod
+    def choice(seq, p=None):
+        if isinstance(seq, int):
+            population = list(range(seq))
+        else:
+            population = list(seq)
+        if not population:
+            raise IndexError("Cannot choose from an empty sequence")
+        if p is None:
+            return _random.choice(population)
+        # ensure probabilities sum to 1
+        total = sum(p)
+        if total <= 0:
+            return _random.choice(population)
+        cumulative = []
+        acc = 0.0
+        for weight in p:
+            acc += weight / total
+            cumulative.append(acc)
+        r = _random.random()
+        for idx, boundary in enumerate(cumulative):
+            if r <= boundary:
+                return population[idx]
+        return population[-1]
+
+
+random = RandomModule()
