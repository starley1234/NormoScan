import logging, collections, time, json, os

# Кольцевой буфер логов в памяти + файл
BUFFER_SIZE = 2000
_buffer = collections.deque(maxlen=BUFFER_SIZE)

class BufferHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            _buffer.append({
                "ts": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(record.created)),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
                "raw": msg
            })
            # также пишем в файл для docker logs + persist
            log_path = os.path.join("storage", "logs", "app.log")
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(msg + "\n")
            except:
                pass
        except:
            pass

_handler = BufferHandler()
_handler.setLevel(logging.INFO)
_formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
_handler.setFormatter(_formatter)

def get_buffer():
    return list(_buffer)

def attach_to_root():
    root = logging.getLogger()
    # не дублировать
    if _handler not in root.handlers:
        root.addHandler(_handler)

def clear_buffer():
    _buffer.clear()
