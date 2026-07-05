"""
算力节点检测引擎

自动检测本机/远程 GPU、CPU、RAM、磁盘等硬件信息
支持 nvidia-smi 解析、CUDA 检测、实时资源监控
"""
import os
import re
import subprocess
import platform
import shutil
from typing import Optional
from loguru import logger


def _run_cmd(cmd: str, timeout: int = 10) -> str:
    """运行命令并返回 stdout，失败返回空串"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"Command failed: {cmd} → {e}")
        return ""


def _run_remote_cmd(ssh_target: str, cmd: str, ssh_key: str = "", port: int = 22, timeout: int = 15) -> str:
    """通过 SSH 在远程节点执行命令"""
    ssh_parts = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
    if ssh_key:
        ssh_parts += ["-i", ssh_key]
    ssh_parts += ["-p", str(port), ssh_target, cmd]
    try:
        result = subprocess.run(ssh_parts, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except Exception as e:
        logger.debug(f"SSH command failed: {cmd} → {e}")
        return ""


def detect_gpus() -> dict:
    """检测 GPU 信息，返回 nvidia-smi 解析结果

    Returns:
        {
            "count": int,
            "model": str,            # e.g. "NVIDIA GeForce RTX 4090"
            "total_vram_gb": float,   # 总显存
            "cuda_version": str,      # e.g. "12.4"
            "gpus": [{"index", "model", "vram_gb", "uuid"}]
        }
    """
    result = {"count": 0, "model": "", "total_vram_gb": 0.0, "cuda_version": "", "gpus": []}

    # 方式1: nvidia-smi (最可靠)
    nvidia_smi = shutil.which("nvidia-smi") or _run_cmd("which nvidia-smi")
    if nvidia_smi or _run_cmd("nvidia-smi -L", timeout=5):
        # GPU 列表
        gpu_list_output = _run_cmd("nvidia-smi --query-gpu=index,name,memory.total,uuid --format=csv,noheader,nounits", timeout=10)
        if gpu_list_output:
            total_vram = 0
            models = set()
            for line in gpu_list_output.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    idx = int(parts[0])
                    name = parts[1]
                    vram_mb = int(parts[2])
                    uuid = parts[3]
                    vram_gb = round(vram_mb / 1024, 1)
                    total_vram += vram_gb
                    models.add(name)
                    result["gpus"].append({
                        "index": idx, "model": name, "vram_gb": vram_gb, "uuid": uuid
                    })
            result["count"] = len(result["gpus"])
            result["model"] = " + ".join(models) if models else ""
            result["total_vram_gb"] = round(total_vram, 1)

        # CUDA 版本
        cuda_output = _run_cmd("nvidia-smi --query-gpu=driver_version --format=csv,noheader", timeout=5)
        nvcc = _run_cmd("nvcc --version", timeout=5)
        if nvcc:
            # 从 nvcc 输出提取 CUDA 版本
            match = re.search(r"release (\d+\.\d+)", nvcc)
            if match:
                result["cuda_version"] = match.group(1)
        elif cuda_output:
            result["cuda_version"] = cuda_output.split("\n")[0]

        logger.info(f"Detected {result['count']} GPU(s): {result['model']} ({result['total_vram_gb']}GB VRAM)")
    else:
        logger.info("No NVIDIA GPU detected (nvidia-smi not found)")

    return result


def get_gpu_stats() -> dict:
    """获取 GPU 实时利用率、显存、温度"""
    stats = {"utilization": 0.0, "vram_used_gb": 0.0, "temp": 0.0, "vram_total_gb": 0.0}

    output = _run_cmd(
        "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu "
        "--format=csv,noheader,nounits", timeout=5
    )
    if output:
        lines = output.strip().split("\n")
        if lines:
            parts = [p.strip() for p in lines[0].split(",")]
            if len(parts) >= 4:
                stats["utilization"] = float(parts[0])
                stats["vram_used_gb"] = round(float(parts[1]) / 1024, 2)
                stats["vram_total_gb"] = round(float(parts[2]) / 1024, 2)
                stats["temp"] = float(parts[3])

    return stats


def detect_cpu() -> dict:
    """检测 CPU 信息"""
    cpu_count = os.cpu_count() or 1
    model_name = platform.processor() or "Unknown CPU"
    return {"count": cpu_count, "model": model_name}


def get_cpu_stats() -> float:
    """获取 CPU 实时利用率 (%)"""
    if platform.system() == "Windows":
        # Windows: 用 wmic
        output = _run_cmd("wmic cpu get loadpercentage /value", timeout=5)
        if output:
            match = re.search(r"LoadPercentage=(\d+)", output)
            if match:
                return float(match.group(1))
    else:
        # Linux: 从 /proc/stat 计算 (简化版)
        output = _run_cmd("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'", timeout=5)
        if output:
            try:
                return float(output.strip("%"))
            except ValueError:
                pass
    return 0.0


def detect_ram() -> dict:
    """检测内存信息"""
    if platform.system() == "Windows":
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return {
            "total_gb": round(stat.ullTotalPhys / (1024**3), 1),
            "used_gb": round((stat.ullTotalPhys - stat.ullAvailPhys) / (1024**3), 1),
            "utilization": float(stat.dwMemoryLoad),
        }
    else:
        output = _run_cmd("free -b", timeout=5)
        if output:
            lines = output.split("\n")
            for line in lines:
                if line.startswith("Mem:"):
                    parts = line.split()
                    total = int(parts[1])
                    used = int(parts[2])
                    return {
                        "total_gb": round(total / (1024**3), 1),
                        "used_gb": round(used / (1024**3), 1),
                        "utilization": round(used / total * 100, 1) if total else 0,
                    }
    return {"total_gb": 0, "used_gb": 0, "utilization": 0.0}


def get_disk_free(path: str = "/") -> float:
    """获取磁盘剩余空间 (GB)"""
    try:
        usage = shutil.disk_usage(path)
        return round(usage.free / (1024**3), 1)
    except Exception:
        return 0.0


def detect_python() -> dict:
    """检测 Python 环境"""
    import sys
    python_path = sys.executable
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # 检测关键库
    libs = {}
    for lib in ["torch", "transformers", "deepspeed", "vllm", "peft", "accelerate"]:
        try:
            mod = __import__(lib)
            libs[lib] = getattr(mod, "__version__", "installed")
        except ImportError:
            libs[lib] = None

    return {"path": python_path, "version": version, "libs": libs}


def full_detect(node_type: str = "local", ssh_target: str = "", ssh_key: str = "", ssh_port: int = 22) -> dict:
    """完整硬件检测

    Args:
        node_type: "local" 或 "remote_ssh"
        ssh_target: SSH 目标 (user@host)
        ssh_key: SSH 私钥路径
        ssh_port: SSH 端口

    Returns: 完整硬件信息 dict
    """
    runner = (lambda cmd: _run_cmd(cmd)) if node_type == "local" else (lambda cmd: _run_remote_cmd(ssh_target, cmd, ssh_key, ssh_port))

    logger.info(f"Running full hardware detection ({node_type})...")

    if node_type == "local":
        gpu_info = detect_gpus()
        gpu_stats = get_gpu_stats()
        cpu_info = detect_cpu()
        cpu_util = get_cpu_stats()
        ram_info = detect_ram()
        disk_free = get_disk_free("/")
        python_info = detect_python()
    else:
        # 远程节点检测
        nvidia_output = runner("nvidia-smi --query-gpu=index,name,memory.total,uuid --format=csv,noheader,nounits")
        gpu_info = {"count": 0, "model": "", "total_vram_gb": 0.0, "cuda_version": "", "gpus": []}
        if nvidia_output:
            total_vram = 0
            models = set()
            for line in nvidia_output.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    idx = int(parts[0])
                    name = parts[1]
                    vram_mb = int(parts[2])
                    vram_gb = round(vram_mb / 1024, 1)
                    total_vram += vram_gb
                    models.add(name)
                    gpu_info["gpus"].append({"index": idx, "model": name, "vram_gb": vram_gb, "uuid": parts[3]})
            gpu_info["count"] = len(gpu_info["gpus"])
            gpu_info["model"] = " + ".join(models) if models else ""
            gpu_info["total_vram_gb"] = round(total_vram, 1)

        # 远程 GPU 实时状态
        gpu_stats_output = runner(
            "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits"
        )
        gpu_stats = {"utilization": 0.0, "vram_used_gb": 0.0, "temp": 0.0, "vram_total_gb": 0.0}
        if gpu_stats_output:
            parts = [p.strip() for p in gpu_stats_output.split("\n")[0].split(",")]
            if len(parts) >= 4:
                gpu_stats = {
                    "utilization": float(parts[0]),
                    "vram_used_gb": round(float(parts[1]) / 1024, 2),
                    "vram_total_gb": round(float(parts[2]) / 1024, 2),
                    "temp": float(parts[3]),
                }

        # 远程 CPU
        cpu_count_output = runner("nproc")
        cpu_info = {"count": int(cpu_count_output) if cpu_count_output.isdigit() else 1, "model": "remote"}

        # 远程 RAM
        ram_output = runner("free -b")
        ram_info = {"total_gb": 0, "used_gb": 0, "utilization": 0.0}
        if ram_output:
            for line in ram_output.split("\n"):
                if line.startswith("Mem:"):
                    parts = line.split()
                    total = int(parts[1])
                    used = int(parts[2])
                    ram_info = {
                        "total_gb": round(total / (1024**3), 1),
                        "used_gb": round(used / (1024**3), 1),
                        "utilization": round(used / total * 100, 1) if total else 0,
                    }

        # 远程磁盘
        disk_output = runner("df -BG / --output=avail | tail -1")
        disk_free = float(disk_output.strip().rstrip("G")) if disk_output.strip() else 0.0

        # 远程 Python
        python_path = runner("which python3") or "python3"
        python_info = {"path": python_path, "version": "", "libs": {}}

    result = {
        "gpu": gpu_info,
        "gpu_stats": gpu_stats,
        "cpu": cpu_info,
        "cpu_util": cpu_util if node_type == "local" else 0.0,
        "ram": ram_info,
        "disk_free_gb": disk_free,
        "python": python_info,
    }

    logger.info(f"Detection complete: {gpu_info['count']} GPU(s), {cpu_info['count']} CPU cores, {ram_info.get('total_gb', 0)}GB RAM")
    return result
