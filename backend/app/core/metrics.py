import threading
import time
from collections import Counter as CounterCls
from collections import defaultdict


# Simple in-memory metrics (Prometheus-like). For prod, expose via prometheus_client.
class Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.counters: dict[str,int] = CounterCls()
        self.histograms: dict[str,list] = defaultdict(list)
        self.gauges: dict[str,float] = {}
        self.start = time.time()

    def inc(self, name: str, value:int=1, labels:dict=None):
        key = name if not labels else f"{name}{{{','.join(f'{k}={v}' for k,v in labels.items())}}}"
        with self.lock:
            self.counters[key]+=value

    def observe(self, name:str, value:float):
        with self.lock:
            self.histograms[name].append(value)
            # keep last 1000
            if len(self.histograms[name])>1000:
                self.histograms[name]=self.histograms[name][-1000:]

    def set(self, name:str, value:float):
        with self.lock:
            self.gauges[name]=value

    def snapshot(self):
        with self.lock:
            # compute histogram stats
            hist_stats={}
            for k, vals in self.histograms.items():
                if vals:
                    hist_stats[k]={"count":len(vals),"avg":sum(vals)/len(vals),"p95": sorted(vals)[int(len(vals)*0.95)] if len(vals)>5 else vals[-1],"max":max(vals),"min":min(vals)}
                else:
                    hist_stats[k]={"count":0}
            return {
                "uptime_seconds": round(time.time()-self.start,1),
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histograms": hist_stats,
            }

    def prometheus_text(self):
        snap = self.snapshot()
        lines=[]
        for k,v in snap["counters"].items():
            # sanitize
            name = k.split("{")[0]
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {v}")
        for k,v in snap["gauges"].items():
            lines.append(f"# TYPE {k} gauge")
            lines.append(f"{k} {v}")
        for k,stats in snap["histograms"].items():
            lines.append(f"# TYPE {k}_avg gauge")
            lines.append(f"{k}_avg {stats.get('avg',0)}")
        return "\n".join(lines)

metrics = Metrics()

# Convenience helpers
def inc_checks(status:str):
    metrics.inc("normoscan_checks_total", labels={"status":status})
    metrics.inc(f"normoscan_checks_{status}")

def observe_page_time(sec:float):
    metrics.observe("normoscan_page_seconds", sec)

def set_queue_depth(depth:int):
    metrics.set("normoscan_queue_depth", depth)

def set_vram_usage(gb:float):
    metrics.set("normoscan_vram_gb", gb)
