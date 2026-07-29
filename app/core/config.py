import os
import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 定义一个正则表达式，用于校验环境变量名称是否合法（仅允许小写字母、数字、下划线和连字符）
# 这是为了防止路径穿越或注入攻击等安全问题
_ENVIRONMENT_NAME = re.compile(r"^[a-z0-9_-]+$")


class Settings(BaseSettings):
    """
    应用全局配置类，继承自 pydantic_settings 的 BaseSettings。
    支持从环境变量和 .env 文件中自动加载并验证配置项。
    """

    # Pydantic 模型配置：指定加载 .env 文件，设置编码，忽略多余字段，并且不区分大小写
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ==========================================
    # 基础应用配置 (Application Settings)
    # ==========================================
    # 运行环境，默认为开发环境 "development"
    app_env: str = "development"
    # 是否开启调试模式
    app_debug: bool = False
    # 应用名称
    app_name: str = "TradePilot"
    # 应用版本
    app_version: str = "0.1.0"
    # 应用自身的 API 密钥，可用于简单的鉴权
    app_api_key: str | None = None

    # ==========================================
    # 数据库与存储路径配置 (Database & Storage Settings)
    # ==========================================
    # 关系型数据库连接 URL，默认使用本地 SQLite
    database_url: str = "sqlite:///data/tradepilot.db"
    # 向量数据库 Chroma 的目录
    chroma_dir: Path = Path("data/chroma")
    # Chroma 数据库持久化保存的目录
    chroma_persist_dir: Path = Path("data/chroma")
    # Chroma 中用于存储商品知识的集合名称
    chroma_product_collection: str = "product_knowledge"
    # Chroma 中用于存储评论洞察的集合名称
    chroma_review_collection: str = "review_insight"
    # 文件上传保存目录
    upload_dir: Path = Path("data/uploads")
    # 报告生成保存目录
    report_dir: Path = Path("data/reports")

    # ==========================================
    # 大语言模型 API 配置 (LLM API Settings)
    # ==========================================
    # OpenAI 配置
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    # DeepSeek 配置（默认请求地址）
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"

    # 阿里千问 (Qwen) 配置（默认请求地址）
    qwen_api_key: str | None = None
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # 根据任务复杂度指定不同的模型名称
    model_fast: str | None = None      # 快速响应模型
    model_analysis: str | None = None  # 深度分析模型
    model_report: str | None = None    # 报告生成模型
    model_vision: str | None = None    # 视觉/多模态模型

    # 模型生成的温度参数，越低越确定，越高越具创造性
    model_temperature: float = 0.1
    # 模型请求超时时间（秒）
    model_timeout_seconds: int = 120
    # 模型请求失败的最大重试次数
    model_max_retries: int = 3
    # 模型解析结果失败时的最大重试次数（限制在 0-2 之间）
    model_parse_max_retries: int = Field(default=1, ge=0, le=2)
    # 模型单次生成的最大 Token 数量
    model_max_tokens: int = 4096

    # ==========================================
    # 向量模型与重排序配置 (Embedding & Rerank Settings)
    # ==========================================
    # 文本向量化模型名称
    embedding_model: str | None = None
    # 运行向量模型的设备 (如 "cpu", "cuda")
    embedding_device: str = "cpu"

    # 重排序 (Rerank) 模型相关配置
    rerank_model: str | None = None
    rerank_base_url: str | None = None
    rerank_enabled: bool = False       # 是否全局启用重排序
    rerank_required: bool = False      # 是否强制要求重排序
    rerank_policy: str = "conditional" # 重排序策略（如 conditional：条件触发）
    rerank_product_enabled: bool = False # 是否对商品检索启用重排序
    rerank_review_enabled: bool = True   # 是否对评论检索启用重排序
    rerank_min_candidates: int = 8       # 重排序候选最小数量
    rerank_max_candidates: int = 20      # 重排序候选最大数量
    rerank_timeout_seconds: int = 40     # 重排序请求超时时间（秒）
    rerank_max_retries: int = 3          # 重排序失败重试次数

    # ==========================================
    # 检索增强生成 (RAG) 参数配置 (RAG Settings)
    # ==========================================
    # RAG 初始检索的数量 (fetch_k 通常大于 top_k)
    rag_fetch_k: int = 30
    rag_product_fetch_k: int = 30
    rag_review_fetch_k: int = 30
    # RAG 最终保留的 Top K 数量
    rag_top_k: int = 8
    # 检索相关性分数阈值，低于该分数的将被过滤
    rag_score_threshold: float = 0.0

    # 是否启用 MMR (最大边际相关性) 算法以增加检索结果多样性
    rag_mmr_enabled: bool = True
    # MMR 算法中的 lambda 参数，平衡相关性与多样性
    rag_mmr_lambda: float = Field(default=0.7, ge=0, le=1)

    # RAG 查询失败重试配置
    rag_query_max_retries: int = Field(default=3, ge=1, le=5)
    rag_query_retry_delay_seconds: float = Field(default=0.1, ge=0, le=2)

    # 各种来源允许的最大检索数量及最少证据要求
    rag_max_per_source: int = 3
    rag_min_product_evidence: int = 1
    rag_min_review_evidence: int = 3

    # RAG 处理过程中的批处理大小及并发数配置
    rag_batch_size: int = 128
    rag_embedding_batch_size: int = 32
    rag_embedding_concurrency: int = 4
    rag_index_batch_size: int = 32

    # 文档切块大小与重叠量设置
    rag_chunk_size: int = 2800
    rag_chunk_overlap: int = 300

    # RAG 存储相关：是否使用 Chroma 向量库，以及本地 SQLite 清单文件路径
    rag_use_chroma: bool = False
    rag_manifest_path: Path = Path("data/index_manifest.sqlite")

    # ==========================================
    # 外部数据源与业务特定的文件路径 (Business Data & Paths)
    # ==========================================
    # 竞品元数据与评论数据路径
    peer_metadata_path: Path = Path("data/filtered/meta_pet_supplies_prefiltered.jsonl")
    peer_reviews_path: Path = Path("data/filtered/pet_supplies_reviews_prefiltered.jsonl")
    # 竞品分析缓存目录
    peer_cache_dir: Path = Path("data/demo/cache")
    # 竞品匹配规则配置文件路径
    peer_match_config_path: Path = Path("config/peer_matching.yaml")

    # 贸易关税 (HS 编码) 映射及数据库路径
    trade_hs_mapping_path: Path = Path("config/trade/hs_mapping.yaml")
    trade_tariff_db_path: Path = Path("data/external/serving/tariff_rules.sqlite")

    # 竞品分析最多处理的评论数
    peer_max_reviews: int = 300

    # ==========================================
    # 运行时及其他配置 (Runtime & Miscellaneous)
    # ==========================================
    # 运行的 Worker 进程数，默认2个，范围 1-8
    run_worker_count: int = Field(default=2, ge=1, le=8)
    # SSE (Server-Sent Events) 轮询间隔时间 (秒)
    sse_poll_interval_seconds: float = Field(default=0.1, gt=0, le=5)
    # SSE 心跳发送间隔时间 (秒)
    sse_heartbeat_seconds: float = Field(default=10, gt=0, le=60)
    # 系统日志级别 (如 DEBUG, INFO, WARNING 等)
    log_level: str = "INFO"
    # 默认数据模式，通常用于区分是测试演示环境 ("demo") 还是生产环境
    default_data_mode: str = Field(default="demo")

    @property
    def real_model_configured(self) -> bool:
        """
        判断系统是否已配置了真实可用的大语言模型。
        检查条件：
        1. 提供了 DeepSeek 密钥，并且配置了三个核心模型（分析、快速、报告）；
        2. 或作为遗留支持，提供了 OpenAI 密钥并配置了分析模型。
        """
        provider_models = bool(
            self.deepseek_api_key
            and self.model_analysis
            and self.model_fast
            and self.model_report
        )
        legacy_single_provider = bool(self.openai_api_key and self.model_analysis)
        return provider_models or legacy_single_provider


def environment_dotenv_files() -> tuple[Path, Path]:
    """
    确定需要加载的 dotenv 文件列表（例如 .env 和 .env.development）。
    该函数会防止路径穿越漏洞，确保应用按照当前环境变量 (APP_ENV) 加载对应的配置文件。
    """
    # 优先从系统环境变量获取 APP_ENV，其次从 .env 文件读取，默认为 "development"
    environment = os.getenv("APP_ENV") or _read_dotenv_value(Path(".env"), "APP_ENV") or "development"
    normalized = environment.strip().lower()

    # 使用正则表达式校验环境名称，确保安全
    if not _ENVIRONMENT_NAME.fullmatch(normalized):
        raise ValueError("APP_ENV must contain only lowercase letters, digits, '_' or '-'")

    # 返回通用配置 .env 和环境特定配置 .env.{environment}
    return Path(".env"), Path(f".env.{normalized}")


def _read_dotenv_value(path: Path, key: str) -> str | None:
    """
    手动从指定的 .env 文件中解析并提取特定键 (key) 的值。
    这是一个轻量级的辅助函数，避免在完全加载配置前需要用到个别变量。
    """
    if not path.is_file():
        return None

    # 逐行读取并解析文件内容，忽略注释和空行
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        # 移除前缀 (如果包含 export) 并按等号拆分
        name, value = line.removeprefix("export ").split("=", 1)
        if name.strip() == key:
            # 去除两端空白字符及引号
            return value.strip().strip("'\"")
    return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    使用 LRU 缓存获取 Settings 单例实例。
    确保在应用生命周期内，Settings 只会被实例化一次，提高性能并保证配置一致性。
    """
    # 初始化 Settings 时，传入解析好的 dotenv 文件列表供 Pydantic 加载
    return Settings(_env_file=environment_dotenv_files())
