"""
Teacher 数据生成 - 使用 GLM API 或本地模型生成 soft labels

用于 Response-based KD:
1. 调用 GLM-4-Plus / GLM-5 API 在训练数据上推理
2. 生成 Teacher 的 response 作为 Student 的训练目标
3. 支持批量并发调用
"""
import os
import json
import asyncio
from typing import Optional
from loguru import logger

# ------------------------------------------------------------------
# Zhipu GLM API 数据生成
# ------------------------------------------------------------------
async def generate_with_glm_api(
    api_key: str,
    prompts: list[str],
    model: str = "glm-4-plus",
    temperature: float = 0.7,
    max_tokens: int = 2048,
    batch_size: int = 5,
) -> list[str]:
    """调用智谱 API 批量生成 Teacher response"""
    from zhipuai import AsyncZhipuAI

    client = AsyncZhipuAI(api_key=api_key)
    results = [None] * len(prompts)

    async def call_one(idx: int, prompt: str):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            results[idx] = response.choices[0].message.content
        except Exception as e:
            logger.error(f"API call failed for prompt {idx}: {e}")
            results[idx] = ""

    # 批量并发
    for i in range(0, len(prompts), batch_size):
        batch = [(i + j, prompts[i + j]) for j in range(min(batch_size, len(prompts) - i))]
        await asyncio.gather(*[call_one(idx, p) for idx, p in batch])
        logger.info(f"Generated {min(i + batch_size, len(prompts))}/{len(prompts)}")

    return results


# ------------------------------------------------------------------
# 本地 Teacher 模型生成 (GLM-4-9B-Chat)
# ------------------------------------------------------------------
def generate_with_local_model(
    model_path: str,
    prompts: list[str],
    temperature: float = 0.7,
    max_new_tokens: int = 2048,
    batch_size: int = 4,
) -> list[str]:
    """使用本地加载的 GLM 模型批量生成"""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    logger.info(f"Loading local teacher model: {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()

    results = []
    for i in range(0, len(prompts), batch_size):
        batch = prompts[i : i + batch_size]
        inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=2048)
        inputs = {k: v.cuda() for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                pad_token_id=tokenizer.pad_token_id,
            )

        for j, output in enumerate(outputs):
            input_len = inputs["input_ids"][j].shape[0]
            generated = tokenizer.decode(output[input_len:], skip_special_tokens=True)
            results.append(generated)

        logger.info(f"Generated {min(i + batch_size, len(prompts))}/{len(prompts)}")

    return results


# ------------------------------------------------------------------
# 数据生成管线
# ------------------------------------------------------------------
def generate_teacher_data(
    dataset_path: str,
    output_path: str,
    teacher_source: str = "api",        # "api" or "local"
    api_key: Optional[str] = None,
    api_model: str = "glm-4-plus",
    local_model_path: Optional[str] = None,
    prompt_field: str = "prompt",
    batch_size: int = 5,
):
    """生成 Teacher soft labels 数据集

    输入格式: JSONL, 每行 {"prompt": "...", "input": "...", ...}
    输出格式: JSONL, 每行 {"prompt": "...", "teacher_response": "..."}
    """
    # Load input data
    data = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                data.append(item)

    prompts = [item.get(prompt_field, item.get("input", "")) for item in data]
    logger.info(f"Loaded {len(prompts)} prompts from {dataset_path}")

    # Generate
    if teacher_source == "api":
        if not api_key:
            raise ValueError("API key required for API-based generation")
        responses = asyncio.run(generate_with_glm_api(
            api_key=api_key, prompts=prompts, model=api_model, batch_size=batch_size
        ))
    elif teacher_source == "local":
        if not local_model_path:
            raise ValueError("local_model_path required for local generation")
        responses = generate_with_local_model(
            model_path=local_model_path, prompts=prompts, batch_size=batch_size
        )
    else:
        raise ValueError(f"Unknown teacher_source: {teacher_source}")

    # Save
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for prompt, response in zip(prompts, responses):
            f.write(json.dumps({"prompt": prompt, "teacher_response": response}, ensure_ascii=False) + "\n")

    logger.info(f"Saved {len(responses)} teacher responses to {output_path}")
    return output_path
