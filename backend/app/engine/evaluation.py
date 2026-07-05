"""
模型评估引擎

评估指标:
- Perplexity: 困惑度
- BLEU: 机器翻译质量
- ROUGE-L: 摘要质量
- Inference Latency: 推理延迟
- Model Size: 模型大小
"""
import os
import time
import torch
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer
from loguru import logger


def evaluate_model(
    model_path: str,
    eval_dataset_path: str | None = None,
    num_samples: int = 100,
) -> dict:
    """完整模型评估"""
    metrics = {}

    # ─── 1. 模型大小 ───
    metrics["model_size_mb"] = _compute_model_size(model_path)

    # ─── 2. 加载模型 ───
    logger.info(f"Loading model for evaluation: {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()

    # ─── 3. Perplexity ───
    if eval_dataset_path and os.path.exists(eval_dataset_path):
        metrics["perplexity"] = _compute_perplexity(model, tokenizer, eval_dataset_path, num_samples)
    else:
        # 使用默认文本计算
        default_text = "人工智能是计算机科学的一个分支，它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。"
        metrics["perplexity"] = _compute_perplexity_single(model, tokenizer, default_text)

    # ─── 4. 推理延迟 ───
    metrics["inference_latency_ms"] = _measure_inference_latency(model, tokenizer)

    # ─── 5. BLEU & ROUGE (如果有评测数据) ───
    if eval_dataset_path and os.path.exists(eval_dataset_path):
        bleu, rouge_l = _compute_text_metrics(model, tokenizer, eval_dataset_path, num_samples)
        metrics["bleu"] = bleu
        metrics["rouge_l"] = rouge_l

    logger.info(f"Evaluation metrics: {metrics}")
    return metrics


def _compute_model_size(model_path: str) -> float:
    """计算模型文件大小 (MB)"""
    total = 0
    for f in os.listdir(model_path):
        if f.endswith((".bin", ".safetensors")):
            total += os.path.getsize(os.path.join(model_path, f))
    return round(total / (1024 * 1024), 2)


@torch.no_grad()
def _compute_perplexity(model, tokenizer, data_path: str, num_samples: int) -> float:
    """在数据集上计算 Perplexity"""
    import json

    losses = []
    with open(data_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= num_samples:
                break
            if not line.strip():
                continue
            item = json.loads(line)
            text = item.get("prompt", "") + item.get("response", item.get("teacher_response", ""))

            inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=2048)
            inputs = {k: v.cuda() for k, v in inputs.items()}

            outputs = model(**inputs, labels=inputs["input_ids"])
            losses.append(outputs.loss.item())

    return round(float(np.exp(np.mean(losses))), 4) if losses else 0.0


@torch.no_grad()
def _compute_perplexity_single(model, tokenizer, text: str) -> float:
    """单条文本的 Perplexity"""
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=2048)
    inputs = {k: v.cuda() for k, v in inputs.items()}
    outputs = model(**inputs, labels=inputs["input_ids"])
    return round(float(torch.exp(outputs.loss)), 4)


@torch.no_grad()
def _measure_inference_latency(model, tokenizer, num_runs: int = 10) -> float:
    """测量推理延迟 (ms/token)"""
    test_prompt = "请解释什么是大模型蒸馏技术。"
    inputs = tokenizer(test_prompt, return_tensors="pt").to(model.device)

    # Warmup
    model.generate(**inputs, max_new_tokens=50, do_sample=False)

    latencies = []
    for _ in range(num_runs):
        start = time.time()
        model.generate(**inputs, max_new_tokens=100, do_sample=False)
        latencies.append((time.time() - start) * 1000 / 100)  # ms per token

    return round(float(np.mean(latencies)), 2)


def _compute_text_metrics(model, tokenizer, data_path: str, num_samples: int) -> tuple:
    """计算 BLEU 和 ROUGE-L"""
    import json
    import jieba
    from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
    from rouge_chinese import Rouge

    bleu_scores = []
    rouge_scores = []

    smooth = SmoothingFunction().method1
    rouge = Rouge()

    with open(data_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= num_samples:
                break
            if not line.strip():
                continue
            item = json.loads(line)
            prompt = item.get("prompt", "")
            reference = item.get("response", item.get("teacher_response", ""))

            # Generate
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            output = model.generate(**inputs, max_new_tokens=256, do_sample=False)
            generated = tokenizer.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

            # BLEU
            ref_tokens = list(jieba.cut(reference))
            gen_tokens = list(jieba.cut(generated))
            if ref_tokens and gen_tokens:
                bleu = sentence_bleu([ref_tokens], gen_tokens, smoothing_function=smooth)
                bleu_scores.append(bleu)

            # ROUGE
            if reference.strip() and generated.strip():
                try:
                    scores = rouge.get_scores(" ".join(gen_tokens), " ".join(ref_tokens))
                    rouge_scores.append(scores[0]["rouge-l"]["f"])
                except:
                    pass

    bleu = round(float(np.mean(bleu_scores)), 4) if bleu_scores else 0.0
    rouge_l = round(float(np.mean(rouge_scores)), 4) if rouge_scores else 0.0
    return bleu, rouge_l
