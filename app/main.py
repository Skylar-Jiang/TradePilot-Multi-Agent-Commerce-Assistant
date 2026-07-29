# 导入异步上下文管理器，用于在 FastAPI 应用启动和关闭时执行特定代码（如数据库升级、资源清理）
from contextlib import asynccontextmanager
# 导入路径操作库，用于创建目录等文件系统操作
from pathlib import Path
# 导入高精度时间计数器，用于计算请求处理耗时
from time import perf_counter
# 导入 uuid4 用于生成唯一的请求 ID
from uuid import uuid4

# 导入 FastAPI 核心应用类和 Request 对象
from fastapi import FastAPI, Request
# 导入请求数据验证异常类，用于处理请求参数不合法的情况
from fastapi.exceptions import RequestValidationError
# 导入 SQLAlchemy 的引擎创建和事件监听模块
from sqlalchemy import create_engine, event
# 导入 sessionmaker，用于创建数据库会话工厂
from sqlalchemy.orm import sessionmaker

# 导入统一的失败响应处理函数
from app.api.responses import failure
# 导入 v1 版本的 API 路由
from app.api.v1.router import router
# 导入后台任务提供者的默认注册表构建器
from app.background.providers import build_default_background_registry
# 导入后台任务提供者注册表类型
from app.background.registry import BackgroundProviderRegistry
# 导入配置设置模型和获取配置的依赖函数
from app.core.config import Settings, get_settings
# 导入项目中自定义的基础异常类
from app.core.exceptions import TradePilotError
# 导入日志配置和 HTTP 请求日志记录函数
from app.core.logging import configure_logging, log_http_request
# 导入数据库迁移函数，用于自动升级数据库模式
from app.db.migrations import upgrade_database
# 导入知识库（RAG）工厂类型及默认创建函数
from app.rag.factory import KnowledgeStoreFactory, create_knowledge_store
# 导入基于内存的知识库实现（通常用于测试或特定场景）
from app.rag.in_memory import InMemoryKnowledgeStore
# 导入运行调度器，用于管理和调度后台的 Agent 任务
from app.services.run_dispatcher import RunDispatcher
# 导入统计提供者工厂类型及默认创建函数
from app.statistics.factory import StatisticsProviderFactory, create_statistics_provider


def create_app(
    settings: Settings | None = None,
    *,
    knowledge_store_factory: KnowledgeStoreFactory = create_knowledge_store,
    statistics_provider_factory: StatisticsProviderFactory = create_statistics_provider,
    background_registry: BackgroundProviderRegistry | None = None,
) -> FastAPI:
    """
    创建并配置 FastAPI 应用实例的工厂函数。
    通过这种工厂模式，可以方便地在测试和生产环境中注入不同的依赖（如配置、知识库、数据库等）。
    """
    # 解析配置：如果未提供则使用系统默认的配置（读取环境变量）
    resolved = settings or get_settings()
    # 检查是否使用了默认的知识库创建工厂
    uses_default_knowledge_store = knowledge_store_factory is create_knowledge_store

    # 配置全局日志级别
    configure_logging(resolved.log_level)

    # === 数据库配置区块 ===
    # 如果使用 SQLite，需要禁用 check_same_thread，并设置超时，以支持多线程访问
    connect_args = (
        {"check_same_thread": False, "timeout": 30}
        if resolved.database_url.startswith("sqlite")
        else {}
    )
    # 创建 SQLAlchemy 数据库引擎，echo 属性根据应用调试模式决定是否打印 SQL 语句
    engine = create_engine(resolved.database_url, connect_args=connect_args, echo=resolved.app_debug)

    # 针对基于文件的 SQLite 数据库，进行特定的性能优化配置（不包含内存数据库）
    if resolved.database_url.startswith("sqlite") and ":memory:" not in resolved.database_url:
        @event.listens_for(engine, "connect")
        def configure_sqlite_connection(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            # 开启 WAL (Write-Ahead Logging) 模式，提升 SQLite 并发读写性能
            cursor.execute("PRAGMA journal_mode=WAL")
            # 设置数据库被锁定时等待的超时时间（毫秒）
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    # 创建数据库会话工厂，禁用自动刷新和提交后对象过期
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # === 知识库（RAG）工厂函数区块 ===
    def worker_knowledge_store():  # type: ignore[no-untyped-def]
        """
        为后台工作节点创建知识库实例。
        如果使用的是默认工厂，则传入当前解析的配置；否则直接调用传入的自定义工厂。
        """
        return (
            create_knowledge_store(resolved)
            if knowledge_store_factory is create_knowledge_store
            else knowledge_store_factory()
        )

    def demo_worker_knowledge_store():  # type: ignore[no-untyped-def]
        """
        为演示场景创建知识库实例。
        如果使用的是默认设置，则降级使用内存知识库，否则使用自定义的工作节点知识库。
        """
        return InMemoryKnowledgeStore() if uses_default_knowledge_store else worker_knowledge_store()

    # === 生命周期管理区块 ===
    @asynccontextmanager
    async def lifespan(application: FastAPI):  # type: ignore[no-untyped-def]
        """
        FastAPI 应用的生命周期管理器。
        yield 之前的部分在应用启动时执行，yield 之后的部分在应用关闭时执行。
        """
        # 1. 确保系统所需的所有存储目录都存在，如果不存在则自动创建
        for path in (resolved.upload_dir, resolved.report_dir, resolved.chroma_dir, resolved.chroma_persist_dir):
            Path(path).mkdir(parents=True, exist_ok=True)

        # 2. 自动运行数据库迁移，将数据库结构升级到最新版本
        upgrade_database(resolved.database_url)

        # 3. 将各类全局依赖（配置、数据库会话工厂、知识库、后台任务等）绑定到应用状态（app.state）中，
        # 以便在路由处理函数中通过 request.app.state 进行访问
        application.state.settings = resolved
        application.state.session_factory = session_factory
        # 初始化应用级别的知识库，特定情况下可能使用基于内存的实现
        application.state.knowledge_store = (
            InMemoryKnowledgeStore()
            if knowledge_store_factory is create_knowledge_store and resolved.rag_use_chroma
            else worker_knowledge_store()
        )
        application.state.knowledge_store_factory = worker_knowledge_store
        application.state.statistics_provider_factory = statistics_provider_factory
        application.state.background_registry = background_registry or build_default_background_registry(resolved)

        # 4. 初始化运行调度器（RunDispatcher），用于处理长时间运行的 Agent 任务
        application.state.run_dispatcher = RunDispatcher(
            session_factory=session_factory,
            knowledge_store_factory=worker_knowledge_store,
            settings=resolved,
            statistics_provider_factory=statistics_provider_factory,
            background_registry=application.state.background_registry,
            demo_knowledge_store_factory=demo_worker_knowledge_store,
        )
        # 恢复之前由于系统崩溃或重启而处于挂起（Pending）状态的任务
        application.state.run_dispatcher.recover_pending()

        # 挂起应用，等待接收 HTTP 请求
        yield

        # 5. 应用关闭时的清理工作：安全关闭调度器并释放数据库引擎资源
        application.state.run_dispatcher.shutdown()
        engine.dispose()

    # === 创建 FastAPI 应用实例 ===
    application = FastAPI(
        title="TradePilot Backend",
        version=resolved.app_version,
        description=(
            "Evidence-grounded peer-group analysis for unlisted pet products, with LCEL Agents, RAG, SQL, SSE, "
            "and Markdown/JSON reports."
        ),
        lifespan=lifespan,
    )

    # === 中间件配置区块 ===
    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        """
        请求中间件：为每个 HTTP 请求分配唯一的 Request ID，并记录请求耗时和访问日志。
        """
        # 从请求头中尝试获取 X-Request-ID，如果没有则生成一个新的 UUID
        request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))
        started_at = perf_counter()  # 记录请求开始时间
        try:
            # 将请求传递给下一个处理环节（路由函数）
            response = await call_next(request)
        except Exception as exc:
            # 捕获处理过程中的未处理异常，记录 500 错误日志，然后向上抛出
            log_http_request(
                request_id=request.state.request_id,
                method=request.method,
                path=request.url.path,
                status_code=500,
                started_at=started_at,
                error=exc,
            )
            raise

        # 在响应头中附加 Request ID，方便客户端追踪
        response.headers["X-Request-ID"] = request.state.request_id
        # 记录正常的 HTTP 请求日志
        log_http_request(
            request_id=request.state.request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            started_at=started_at,
        )
        return response

    # === 异常处理配置区块 ===
    @application.exception_handler(TradePilotError)
    async def tradepilot_error(request: Request, exc: TradePilotError):  # type: ignore[no-untyped-def]
        """
        捕获业务层抛出的 TradePilotError 异常，统一转换为标准的失败响应格式。
        """
        return failure(
            request,
            status_code=exc.status_code,
            code=exc.code.value,
            message=exc.message,
            details=exc.details,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):  # type: ignore[no-untyped-def]
        """
        捕获 FastAPI 请求参数验证失败的异常，将其包装为 422 状态码的统一失败响应。
        """
        return failure(
            request,
            status_code=422,
            code="validation_error",
            message="Request validation failed",
            details=exc.errors(),
        )

    # === 注册路由 ===
    # 将 v1 版本的 API 路由集成到当前应用中
    application.include_router(router)

    return application


# 创建全局的 app 实例，供 ASGI 服务器（如 Uvicorn）启动使用
app = create_app()
