-- GLM Distill Platform 数据库初始化

-- 创建 MLflow 数据库
SELECT 'CREATE DATABASE mlflow'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mlflow')\gexec
