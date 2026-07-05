"""ORM 数据模型"""
import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    String, Text, Integer, Float, DateTime, ForeignKey, JSON, Enum, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class DistillStrategy(str, enum.Enum):
    LOGITS_KD = "logits_kd"          # Logits-based 蒸馏
    RESPONSE_KD = "response_kd"      # Response-based 蒸馏
    FEATURE_KD = "feature_kd"        # Feature-based 蒸馏
    MULTI_TEACHER = "multi_teacher"   # 多教师蒸馏
    PROGRESSIVE = "progressive"      # 渐进式蒸馏


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ModelType(str, enum.Enum):
    TEACHER = "teacher"
    STUDENT = "student"
    DISTILLED = "distilled"


class Model(Base):
    """模型仓库"""
    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255))
    model_type: Mapped[ModelType] = mapped_column(Enum(ModelType))
    base_model: Mapped[str] = mapped_column(String(255))   # e.g. THUDM/glm-4-9b-chat
    huggingface_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    minio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parameters: Mapped[int] = mapped_column(Integer, default=0)  # 参数量 (亿)
    description: Mapped[str] = mapped_column(Text, default="")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    distill_tasks: Mapped[list["DistillTask"]] = relationship(
        back_populates="student_model", foreign_keys="DistillTask.student_model_id"
    )


class Dataset(Base):
    """数据集"""
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    format: Mapped[str] = mapped_column(String(50), default="jsonl")  # jsonl, csv, parquet
    num_samples: Mapped[int] = mapped_column(Integer, default=0)
    file_path: Mapped[str] = mapped_column(String(512))      # MinIO path
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    columns: Mapped[dict] = mapped_column(JSON, default=dict)
    tags: Mapped[dict] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    distill_tasks: Mapped[list["DistillTask"]] = relationship(back_populates="dataset")


class DistillTask(Base):
    """蒸馏任务"""
    __tablename__ = "distill_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")

    # 模型
    teacher_model_id: Mapped[str] = mapped_column(ForeignKey("models.id"))
    student_model_id: Mapped[str] = mapped_column(ForeignKey("models.id"))
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))

    # 策略
    strategy: Mapped[DistillStrategy] = mapped_column(Enum(DistillStrategy))
    distill_temperature: Mapped[float] = mapped_column(Float, default=2.0)
    distill_alpha: Mapped[float] = mapped_column(Float, default=0.5)   # KD loss weight
    use_response_data: Mapped[bool] = mapped_column(Boolean, default=False)

    # 训练超参
    learning_rate: Mapped[float] = mapped_column(Float, default=5e-5)
    batch_size: Mapped[int] = mapped_column(Integer, default=4)
    eval_batch_size: Mapped[int] = mapped_column(Integer, default=8)
    num_epochs: Mapped[int] = mapped_column(Integer, default=3)
    max_seq_length: Mapped[int] = mapped_column(Integer, default=2048)
    warmup_steps: Mapped[int] = mapped_column(Integer, default=100)
    save_steps: Mapped[int] = mapped_column(Integer, default=500)
    eval_steps: Mapped[int] = mapped_column(Integer, default=500)
    gradient_accumulation_steps: Mapped[int] = mapped_column(Integer, default=1)
    deepspeed_config: Mapped[str | None] = mapped_column(String(255), nullable=True)
    use_lora: Mapped[bool] = mapped_column(Boolean, default=False)
    lora_rank: Mapped[int] = mapped_column(Integer, default=8)
    lora_alpha: Mapped[int] = mapped_column(Integer, default=32)

    # 状态
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING)
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 ~ 1.0
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 输出
    output_model_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 关系
    student_model: Mapped["Model"] = relationship(back_populates="distill_tasks", foreign_keys=[student_model_id])
    dataset: Mapped["Dataset"] = relationship(back_populates="distill_tasks")
    teacher_model: Mapped["Model"] = relationship(foreign_keys=[teacher_model_id])

    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="task")


class Evaluation(Base):
    """模型评估结果"""
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("distill_tasks.id"))
    eval_dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id"), nullable=True)
    model_path: Mapped[str] = mapped_column(String(512))

    perplexity: Mapped[float | None] = mapped_column(Float, nullable=True)
    bleu: Mapped[float | None] = mapped_column(Float, nullable=True)
    rouge_l: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    inference_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_size_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    custom_metrics: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["DistillTask"] = relationship(back_populates="evaluations")


class Deployment(Base):
    """模型部署记录"""
    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    model_name: Mapped[str] = mapped_column(String(255))
    model_path: Mapped[str] = mapped_column(String(512))
    framework: Mapped[str] = mapped_column(String(50), default="vllm")  # vllm, transformers
    endpoint_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, stopped
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    replicas: Mapped[int] = mapped_column(Integer, default=1)
    gpu_memory_gb: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ComputeNode(Base):
    """算力节点 — 管理本机/远程 GPU 算力连接"""
    __tablename__ = "compute_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255))
    node_type: Mapped[str] = mapped_column(String(20), default="local")  # local, remote_ssh
    host: Mapped[str] = mapped_column(String(255), default="localhost")
    ssh_port: Mapped[int] = mapped_column(Integer, default=22)
    ssh_user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ssh_key_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # 硬件信息
    gpu_count: Mapped[int] = mapped_column(Integer, default=0)
    gpu_model: Mapped[str] = mapped_column(String(255), default="")
    gpu_total_vram_gb: Mapped[float] = mapped_column(Float, default=0)
    cpu_count: Mapped[int] = mapped_column(Integer, default=0)
    ram_total_gb: Mapped[float] = mapped_column(Float, default=0)
    cuda_version: Mapped[str] = mapped_column(String(50), default="")

    # 实时状态
    status: Mapped[str] = mapped_column(String(20), default="offline")  # offline, online, busy, error
    gpu_utilization: Mapped[float] = mapped_column(Float, default=0)   # 0-100
    gpu_vram_used_gb: Mapped[float] = mapped_column(Float, default=0)
    gpu_temp: Mapped[float] = mapped_column(Float, default=0)
    cpu_utilization: Mapped[float] = mapped_column(Float, default=0)
    ram_used_gb: Mapped[float] = mapped_column(Float, default=0)
    disk_free_gb: Mapped[float] = mapped_column(Float, default=0)

    # 当前任务
    current_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    python_path: Mapped[str] = mapped_column(String(512), default="python")
    working_dir: Mapped[str] = mapped_column(String(512), default="/data")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
