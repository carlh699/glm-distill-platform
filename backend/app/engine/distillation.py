"""
蒸馏训练引擎 - GLM Teacher-Student Distillation

支持三种蒸馏策略:
1. Logits-based KD: Teacher 和 Student 都输出 logits, 用 KL 散度对齐
   - 需要能同时加载 Teacher 和 Student 模型
   - Loss = α * KL(softmax(teacher_logits/T), softmax(student_logits/T)) + (1-α) * CE(student, labels)

2. Response-based KD: Teacher 先在数据集上推理生成 soft labels (response),
   Student 在这些 response 上做 SFT
   - 适合 Teacher 通过 API 调用的场景 (GLM-4-Plus / GLM-5)
   - 两阶段: 生成 → 训练

3. Multi-teacher KD: 多个 Teacher 的 logits/response 取平均后蒸馏
"""
import os
import json
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForSeq2Seq,
)
from loguru import logger
from typing import Optional


class DistillationDataset(Dataset):
    """蒸馏训练数据集

    支持两种模式:
    - logits_kd: 每条数据包含 input_ids + labels（用于 logit 级蒸馏）
    - response_kd: 每条数据包含 prompt + teacher_response（Student 做 SFT）
    """

    def __init__(self, data_path: str, tokenizer, max_length: int = 2048, mode: str = "logits_kd"):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.mode = mode
        self.data = []

        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.data.append(json.loads(line))

        logger.info(f"Loaded {len(self.data)} samples from {data_path} (mode={mode})")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]

        if self.mode == "logits_kd":
            # Logits-based KD: tokenize input + label
            prompt = item.get("prompt", item.get("input", ""))
            response = item.get("response", item.get("output", ""))

            full_text = prompt + response
            prompt_ids = self.tokenizer.encode(prompt, add_special_tokens=False)
            full_ids = self.tokenizer.encode(full_text, add_special_tokens=False)

            # Truncate
            full_ids = full_ids[: self.max_length]
            labels = full_ids.copy()
            # Mask prompt tokens
            prompt_len = min(len(prompt_ids), len(full_ids))
            labels[:prompt_len] = [-100] * prompt_len

            return {
                "input_ids": full_ids,
                "labels": labels,
                "attention_mask": [1] * len(full_ids),
            }

        elif self.mode == "response_kd":
            # Response-based KD: Student learns from Teacher's response
            prompt = item.get("prompt", "")
            teacher_response = item.get("teacher_response", item.get("response", ""))

            full_text = prompt + teacher_response
            prompt_ids = self.tokenizer.encode(prompt, add_special_tokens=False)
            full_ids = self.tokenizer.encode(full_text, add_special_tokens=False)

            full_ids = full_ids[: self.max_length]
            labels = full_ids.copy()
            prompt_len = min(len(prompt_ids), len(full_ids))
            labels[:prompt_len] = [-100] * prompt_len

            return {
                "input_ids": full_ids,
                "labels": labels,
                "attention_mask": [1] * len(full_ids),
            }


class DistillationCollator:
    """动态 padding collator"""

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    def __call__(self, batch):
        max_len = max(len(item["input_ids"]) for item in batch)
        input_ids = []
        labels = []
        attention_mask = []

        for item in batch:
            pad_len = max_len - len(item["input_ids"])
            input_ids.append(item["input_ids"] + [self.tokenizer.pad_token_id] * pad_len)
            labels.append(item["labels"] + [-100] * pad_len)
            attention_mask.append(item["attention_mask"] + [0] * pad_len)

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
        }


class DistillationTrainer(Trainer):
    """自定义 Trainer, 实现 Logits-based KD 损失

    Loss = α * T² * KL(softmax(teacher_logits/T), softmax(student_logits/T))
         + (1-α) * CE(student_logits, labels)

    其中 T 是温度参数，T² 用于补偿梯度缩放
    """

    def __init__(self, teacher_model=None, temperature=2.0, alpha=0.5, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher_model = teacher_model
        self.temperature = temperature
        self.alpha = alpha
        if self.teacher_model:
            self.teacher_model.eval()
            for param in self.teacher_model.parameters():
                param.requires_grad = False
            logger.info(f"Teacher model loaded for KD (T={temperature}, α={alpha})")

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        # Student forward pass
        outputs = model(**inputs)
        student_logits = outputs.logits
        labels = inputs["labels"]

        # Cross-entropy loss (hard labels)
        ce_loss = F.cross_entropy(
            student_logits.view(-1, student_logits.size(-1)),
            labels.view(-1),
            ignore_index=-100,
        )

        if self.teacher_model is not None and self.alpha < 1.0:
            # Teacher forward pass (no grad)
            with torch.no_grad():
                teacher_outputs = self.teacher_model(
                    input_ids=inputs["input_ids"],
                    attention_mask=inputs["attention_mask"],
                )
                teacher_logits = teacher_outputs.logits

            # KL divergence loss (soft labels)
            T = self.temperature
            kd_loss = F.kl_div(
                F.log_softmax(student_logits / T, dim=-1),
                F.softmax(teacher_logits / T, dim=-1),
                reduction="batchmean",
            ) * (T * T)

            # Combined loss
            loss = self.alpha * kd_loss + (1 - self.alpha) * ce_loss
        else:
            # No teacher available → pure SFT
            loss = ce_loss

        return (loss, outputs) if return_outputs else loss


def load_model_and_tokenizer(
    model_path: str,
    device_map: str = "auto",
    torch_dtype=torch.float16,
    trust_remote_code: bool = True,
    load_in_4bit: bool = False,
):
    """加载模型和 tokenizer"""
    logger.info(f"Loading model from {model_path}")

    kwargs = {
        "trust_remote_code": trust_remote_code,
        "torch_dtype": torch_dtype,
    }

    if load_in_4bit:
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
    else:
        kwargs["device_map"] = device_map

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(model_path, **kwargs)
    return model, tokenizer


def run_distillation_training(
    task_id: str,
    teacher_model_path: str,
    student_model_path: str,
    dataset_path: str,
    strategy: str = "logits_kd",
    temperature: float = 2.0,
    alpha: float = 0.5,
    learning_rate: float = 5e-5,
    batch_size: int = 4,
    num_epochs: int = 3,
    max_seq_length: int = 2048,
    warmup_steps: int = 100,
    save_steps: int = 500,
    eval_steps: int = 500,
    gradient_accumulation_steps: int = 1,
    use_lora: bool = False,
    lora_rank: int = 8,
    lora_alpha: int = 32,
    output_dir: str = "/data/models/distilled",
    deepspeed_config: Optional[str] = None,
    mlflow_tracking_uri: Optional[str] = None,
    mlflow_run_name: Optional[str] = None,
):
    """执行蒸馏训练的主函数

    Args:
        strategy: logits_kd | response_kd
            - logits_kd: 同时加载 Teacher + Student, logit 级蒸馏
            - response_kd: 仅加载 Student, 在预生成的 Teacher response 上做 SFT
    """
    import time
    from torch.utils.data import random_split

    os.makedirs(output_dir, exist_ok=True)
    run_start = time.time()
    logger.info(f"[Task {task_id}] Starting distillation: {strategy}")

    # ─── 1. 加载 Student 模型 ───
    student_model, tokenizer = load_model_and_tokenizer(student_model_path)
    student_model.config.use_cache = False

    # LoRA
    if use_lora:
        from peft import LoraConfig, get_peft_model, TaskType
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=lora_rank,
            lora_alpha=lora_alpha,
            lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        )
        student_model = get_peft_model(student_model, lora_config)
        student_model.print_trainable_parameters()
        logger.info("LoRA enabled")

    # ─── 2. 加载 Teacher 模型 (仅 logits_kd 策略) ───
    teacher_model = None
    if strategy == "logits_kd":
        teacher_model, _ = load_model_and_tokenizer(teacher_model_path, load_in_4bit=True)
        teacher_model = teacher_model.cuda()
        logger.info("Teacher model loaded for logits-based KD")
    elif strategy == "response_kd":
        logger.info("Response-based KD: using pre-generated teacher responses (SFT mode)")

    # ─── 3. 准备数据集 ───
    mode = "response_kd" if strategy == "response_kd" else "logits_kd"
    dataset = DistillationDataset(dataset_path, tokenizer, max_seq_length, mode=mode)

    # Split 90/10
    train_size = int(0.9 * len(dataset))
    eval_size = len(dataset) - train_size
    train_dataset, eval_dataset = random_split(
        dataset, [train_size, eval_size],
        generator=torch.Generator().manual_seed(42)
    )

    collator = DistillationCollator(tokenizer)

    # ─── 4. 训练参数 ───
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size * 2,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=learning_rate,
        warmup_steps=warmup_steps,
        weight_decay=0.01,
        max_grad_norm=1.0,
        logging_steps=50,
        save_steps=save_steps,
        eval_steps=eval_steps,
        eval_strategy="steps",
        save_total_limit=3,
        bf16=True,
        gradient_checkpointing=True,
        report_to="mlflow" if mlflow_tracking_uri else "none",
        run_name=mlflow_run_name or f"distill-{task_id}",
        deepspeed=deepspeed_config,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
    )

    # ─── 5. 创建 Trainer ───
    trainer = DistillationTrainer(
        model=student_model,
        teacher_model=teacher_model,
        temperature=temperature,
        alpha=alpha,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=collator,
    )

    # ─── 6. 训练 ───
    train_result = trainer.train()

    # ─── 7. 保存模型 ───
    final_dir = os.path.join(output_dir, "final")
    trainer.save_model(final_dir)
    tokenizer.save_pretrained(final_dir)

    # Merge LoRA if needed
    if use_lora:
        merged_model = student_model.merge_and_unload()
        merged_model.save_pretrained(final_dir)
        logger.info("LoRA weights merged and saved")

    # ─── 8. 返回指标 ───
    metrics = {
        "train_loss": train_result.training_loss,
        "train_runtime_sec": train_result.metrics.get("train_runtime", 0),
        "train_samples_per_sec": train_result.metrics.get("train_samples_per_second", 0),
        "total_steps": trainer.state.global_step,
        "output_dir": final_dir,
        "model_size_mb": sum(
            os.path.getsize(os.path.join(final_dir, f)) * 0.001
            for f in os.listdir(final_dir)
            if f.endswith((".bin", ".safetensors"))
        ),
        "wall_time_sec": time.time() - run_start,
    }

    logger.info(f"[Task {task_id}] Distillation complete: {metrics}")
    return metrics
