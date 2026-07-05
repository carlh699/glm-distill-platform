"""Pydantic Schemas - 请求/响应模型"""
from pydantic import BaseModel, Field
from datetime import datetime
from app.models import DistillStrategy, TaskStatus, ModelType


# ─── Model ───
class ModelCreate(BaseModel):
    name: str
    model_type: ModelType
    base_model: str
    huggingface_id: str | None = None
    local_path: str | None = None
    parameters: int = 0
    description: str = ""


class ModelResponse(BaseModel):
    id: str
    name: str
    model_type: ModelType
    base_model: str
    huggingface_id: str | None
    local_path: str | None
    minio_path: str | None
    parameters: int
    description: str
    is_available: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Dataset ───
class DatasetResponse(BaseModel):
    id: str
    name: str
    description: str
    format: str
    num_samples: int
    file_path: str
    file_size: int
    columns: dict
    tags: list
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── DistillTask ───
class DistillTaskCreate(BaseModel):
    name: str
    description: str = ""
    teacher_model_id: str
    student_model_id: str
    dataset_id: str
    strategy: DistillStrategy = DistillStrategy.LOGITS_KD
    distill_temperature: float = Field(2.0, ge=0.1, le=10.0)
    distill_alpha: float = Field(0.5, ge=0.0, le=1.0)
    use_response_data: bool = False
    learning_rate: float = 5e-5
    batch_size: int = 4
    eval_batch_size: int = 8
    num_epochs: int = 3
    max_seq_length: int = 2048
    warmup_steps: int = 100
    save_steps: int = 500
    eval_steps: int = 500
    gradient_accumulation_steps: int = 1
    deepspeed_config: str | None = None
    use_lora: bool = False
    lora_rank: int = 8
    lora_alpha: int = 32


class DistillTaskResponse(BaseModel):
    id: str
    name: str
    description: str
    teacher_model_id: str
    student_model_id: str
    dataset_id: str
    strategy: DistillStrategy
    distill_temperature: float
    distill_alpha: float
    learning_rate: float
    batch_size: int
    num_epochs: int
    max_seq_length: int
    status: TaskStatus
    progress: float
    current_step: int
    total_steps: int
    celery_task_id: str | None
    mlflow_run_id: str | None
    output_model_path: str | None
    metrics: dict
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    model_config = {"from_attributes": True}


class DistillTaskUpdate(BaseModel):
    status: TaskStatus | None = None
    progress: float | None = None
    current_step: int | None = None
    total_steps: int | None = None
    celery_task_id: str | None = None
    mlflow_run_id: str | None = None
    output_model_path: str | None = None
    metrics: dict | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


# ─── Evaluation ───
class EvaluationResponse(BaseModel):
    id: str
    task_id: str
    model_path: str
    perplexity: float | None
    bleu: float | None
    rouge_l: float | None
    accuracy: float | None
    inference_latency_ms: float | None
    model_size_mb: float | None
    custom_metrics: dict
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Deployment ───
class DeploymentCreate(BaseModel):
    model_name: str
    model_path: str
    framework: str = "vllm"
    replicas: int = 1
    config: dict = {}


class DeploymentResponse(BaseModel):
    id: str
    model_name: str
    model_path: str
    framework: str
    endpoint_url: str | None
    status: str
    replicas: int
    gpu_memory_gb: float
    created_at: datetime
    stopped_at: datetime | None
    model_config = {"from_attributes": True}


# ─── ComputeNode ───
class ComputeNodeCreate(BaseModel):
    name: str
    node_type: str = "local"  # local, remote_ssh
    host: str = "localhost"
    ssh_port: int = 22
    ssh_user: str | None = None
    ssh_key_path: str | None = None
    python_path: str = "python"
    working_dir: str = "/data"


class ComputeNodeResponse(BaseModel):
    id: str
    name: str
    node_type: str
    host: str
    ssh_port: int
    ssh_user: str | None
    gpu_count: int
    gpu_model: str
    gpu_total_vram_gb: float
    cpu_count: int
    ram_total_gb: float
    cuda_version: str
    status: str
    gpu_utilization: float
    gpu_vram_used_gb: float
    gpu_temp: float
    cpu_utilization: float
    ram_used_gb: float
    disk_free_gb: float
    current_task_id: str | None
    last_heartbeat: datetime | None
    created_at: datetime
    connected_at: datetime | None
    model_config = {"from_attributes": True}


class ComputeNodeConnect(BaseModel):
    """SSH 连接配置（远程节点）"""
    ssh_user: str | None = None
    ssh_key_path: str | None = None
    ssh_port: int = 22
    python_path: str = "python3"
    working_dir: str = "/data"


class GpuStatsResponse(BaseModel):
    gpu_utilization: float
    gpu_vram_used_gb: float
    gpu_vram_total_gb: float
    gpu_temp: float
    cpu_utilization: float
    ram_used_gb: float
    ram_total_gb: float
    disk_free_gb: float


# ─── 通用 ───
class PaginatedResponse(BaseModel):
    total: int
    items: list
    page: int
    page_size: int


class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: dict | list | None = None
