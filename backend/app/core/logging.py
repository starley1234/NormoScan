import logging, json, sys, time
from ..config import settings

class JsonFormatter(logging.Formatter):
    def format(self, record):
        obj = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            obj["exc_info"] = self.formatException(record.exc_info)
        # extra fields
        for k in ["check_id","page","gost","user","duration"]:
            if hasattr(record, k):
                obj[k]=getattr(record,k)
        return json.dumps(obj, ensure_ascii=False)

def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    if settings.app_env=="production":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    # quiet noisy libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
