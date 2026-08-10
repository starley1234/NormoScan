#!/usr/bin/env python3
"""
Квантование и развертывание модели через vLLM / Ollama / llama.cpp
"""
import argparse, os, subprocess, json

def quantize_awq(model, out):
    print(f"[AWQ] Квантование {model} -> {out}")
    # В реальности: AutoAWQ
    # from awq import AutoAWQForCausalLM
    # model = AutoAWQForCausalLM.from_pretrained(model)
    # model.quantize(...)
    print("Требует GPU 16GB, см. docs/quantization.md")
    # mock
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out,"config.json"),"w") as f:
        json.dump({"model":model,"quant":"awq-4bit"},f)
    print("Done (mock)")

def serve_vllm(model, quant):
    cmd=["python","-m","vllm.entrypoints.openai.api_server","--model",model,"--quantization",quant,"--max-model-len","8192","--gpu-memory-utilization","0.9"]
    print("Запуск:", " ".join(cmd))
    subprocess.run(cmd)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--model", default="google/gemma-3-12b-it")
    p.add_argument("--quant", default="awq-4bit", choices=["awq-4bit","gptq-4bit","int8","fp16"])
    p.add_argument("--out", default="./models/gemma-3-12b-awq")
    p.add_argument("--serve", action="store_true")
    args=p.parse_args()
    if args.serve:
        serve_vllm(args.model, args.quant)
    else:
        quantize_awq(args.model, args.out)
