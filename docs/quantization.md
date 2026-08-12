# Квантование и развертывание (16GB VRAM)

## Поддерживаемые модели

| Модель | Контекст | VRAM FP16 | VRAM 4-bit | Рекомендация |
|--------|----------|-----------|------------|--------------|
| google/gemma-3-12b-it | 32k | ~24GB | ~8-9GB | **Основной** — 12B, AWQ 4-bit, 8192 токенов default |
| google/gemma-3-4b-it | 32k | ~10GB | ~3.5GB | Легкий fallback |
| Qwen/Qwen2-VL-7B-Instruct | 32k | ~16GB | ~5GB | Альтернатива vision |
| Qwen/Qwen2-VL-2B | 32k | ~6GB | ~2GB | Edge |

## Квантование

### AWQ (рекомендуется)
```bash
pip install autoawq
python -m awq.entrypoints.quant --model google/gemma-3-12b-it --w-bit 4 --group-size 128 --out ./models/gemma-3-12b-awq
```

### GPTQ
```bash
pip install auto-gptq optimum
python -m optimum.gptq --model google/gemma-3-12b-it --bits 4 --dataset c4 --out ./models/gemma-3-12b-gptq
```

### bitsandbytes (динамическое, без подготовки)
```python
from transformers import AutoModelForVision2Seq, BitsAndBytesConfig
import torch
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16)
model = AutoModelForVision2Seq.from_pretrained("google/gemma-3-12b-it", quantization_config=bnb, device_map="auto")
```

## Запуск

### vLLM (рекомендуется для сервера)
```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server \
  --model ./models/gemma-3-12b-awq \
  --quantization awq \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.9 \
  --enforce-eager
# Совместим с OpenAI API: http://localhost:8000/v1/chat/completions
```

### SGLang
```bash
pip install sglang
python -m sglang.launch_server --model-path google/gemma-3-12b-it --port 30000 --mem-fraction-static 0.88
```

### Ollama (простота)
```bash
ollama create gemma3:12b -f Modelfile
# Modelfile:
# FROM ./models/gemma-3-12b-awq
# PARAMETER num_ctx 8192
ollama run gemma3:12b
```

### llama.cpp
```bash
./llama.cpp/convert.py --model google/gemma-3-12b-it --outtype q4_0 --outfile gemma-3-12b-q4.gguf
./llama.cpp/llama-server -m gemma-3-12b-q4.gguf --ctx-size 8192 --port 8080
```

## Настройки контекста

В `.env` или Админка:
```
MAX_CONTEXT_WINDOW=8192   # Gemma-3 поддерживает до 32768, но 8192 оптимально для 16GB
IMAGE_WIDTH=768           # 512-800px, больше = больше токенов зрения
VLM_QUANTIZATION=awq-4bit
VRAM_LIMIT_GB=16
EMPTY_CACHE_AFTER_PAGE=true
MAX_CONCURRENT_VLM=1
```

Оценка токенов: изображение 768px ~ 256-400 vision токенов + текст OCR ~200-800 токенов + RAG контекст ~300 токенов + summary_prev ~200 токенов. Укладывается в 8192.

## VRAM оптимизация

- `torch.cuda.empty_cache()` после каждой страницы (вкл. по умолчанию)
- `vLLM` paged attention экономит ~30%
- Pipeline: пока VLM генерирует страницу N, CPU готовит OCR/кроп для N+1
- Ограничить `IMAGE_WIDTH` — главный рычаг
