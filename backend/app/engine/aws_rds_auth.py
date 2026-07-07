"""AWS Aurora IAM 认证连接器

通过 AWS IAM Role 生成临时数据库 token，无需密码。
Vercel 的 AWS integration 就是用这种方式连接 Aurora 的。
"""
import boto3
import datetime
from loguru import logger


def generate_iam_auth_token(
    host: str,
    port: int,
    user: str,
    region: str,
    role_arn: str = "",
) -> str:
    """生成 IAM 认证 token

    Args:
        host: RDS endpoint
        port: 5432
        user: postgres
        region: ap-northeast-1
        role_arn: AWS IAM Role ARN (可选，用于 AssumeRole)
    """
    # 如果有 role_arn，先 assume role
    if role_arn:
        sts = boto3.client("sts")
        assumed = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName="glm-distill-db-connect",
            DurationSeconds=900,
        )
        creds = assumed["Credentials"]
        client = boto3.client(
            "rds",
            region_name=region,
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )
    else:
        client = boto3.client("rds", region_name=region)

    token = client.generate_db_auth_token(
        DBHostname=host,
        Port=port,
        DBUsername=user,
        Region=region,
    )
    logger.info(f"Generated IAM auth token for {user}@{host}:{port} (region={region})")
    return token


def get_connection_string(
    host: str,
    port: int,
    user: str,
    database: str,
    region: str,
    role_arn: str = "",
    sslmode: str = "require",
) -> str:
    """获取带 IAM token 的连接字符串"""
    token = generate_iam_auth_token(host, port, user, region, role_arn)
    # asyncpg 格式
    url = f"postgresql+asyncpg://{user}:{token}@{host}:{port}/{database}?ssl={sslmode}"
    return url


if __name__ == "__main__":
    import os
    host = os.environ.get("PGHOST", "bigmodel.cluster-cry8ei8e6qa0.ap-northeast-1.rds.amazonaws.com")
    port = int(os.environ.get("PGPORT", 5432))
    user = os.environ.get("PGUSER", "postgres")
    database = os.environ.get("PGDATABASE", "postgres")
    region = os.environ.get("AWS_REGION", "ap-northeast-1")
    role_arn = os.environ.get("AWS_ROLE_ARN", "")

    print(f"Host: {host}")
    print(f"User: {user}")
    print(f"Database: {database}")
    print(f"Region: {region}")
    print(f"Role ARN: {role_arn}")
    print()

    try:
        token = generate_iam_auth_token(host, port, user, region, role_arn)
        print(f"IAM Token (first 50): {token[:50]}...")

        # Test connection with psycopg2
        import psycopg2
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=token,
            dbname=database, sslmode="require", connect_timeout=10
        )
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()
        print(f"\n✅ Connected to AWS Aurora!")
        print(f"   PostgreSQL version: {version[0][:60]}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
