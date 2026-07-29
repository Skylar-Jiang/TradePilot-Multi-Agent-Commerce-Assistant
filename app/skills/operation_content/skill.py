from __future__ import annotations

# 导入正则表达式库，用于后续文本清理和提取
import re
# 导入数据类装饰器，用于定义轻量级的数据容器
from dataclasses import dataclass
# 导入路径操作库，用于文件路径的处理
from pathlib import Path
# 导入类型提示相关的 Any
from typing import Any

# 导入 yaml 库，用于解析 YAML 格式的配置文件
import yaml
# 从 pydantic 导入 BaseModel 和 Field，用于定义和校验数据结构（如规则限制）
from pydantic import BaseModel, Field

# 导入产品画像的数据模式，用于生成内容时的输入参考
from app.schemas.product import ProductProfile

# --- 定义内容解析时的文本前缀常量 ---
# 这些前缀用于在生成或提取内容时，区分各部分内容（标题、卖点、描述等）
TITLE_PREFIX = "CONTENT_TITLE: "
BULLET_PREFIX = "CONTENT_BULLET: "
DESCRIPTION_PREFIX = "CONTENT_DESCRIPTION: "
KEYWORDS_PREFIX = "CONTENT_KEYWORDS: "
CUSTOMER_SERVICE_PREFIX = "CUSTOMER_SERVICE_"


# --- 规则模型定义区 ---
# 下列类利用 Pydantic 设定了生成内容的校验规则（例如字符长度、数量限制等）

class TitleRules(BaseModel):
    # 标题规则：长度必须在 40 到 250 个字符之间
    max_chars: int = Field(ge=40, le=250)


class BulletRules(BaseModel):
    # 卖点规则：卖点数量在 3 到 8 个之间，每个卖点长度在 80 到 500 个字符之间
    count: int = Field(ge=3, le=8)
    max_chars: int = Field(ge=80, le=500)


class DescriptionRules(BaseModel):
    # 描述规则：长度在 200 到 3000 个字符之间，并包含一个生成模板
    max_chars: int = Field(ge=200, le=3000)
    template: str


class KeywordRules(BaseModel):
    # 关键词规则：关键词数量限制在 3 到 30 个之间
    max_items: int = Field(ge=3, le=30)


class ContentRules(BaseModel):
    # 整体内容规则：组合了上述的各项具体规则
    title: TitleRules
    bullets: BulletRules
    description: DescriptionRules
    keywords: KeywordRules
    # 违禁营销词汇列表，默认为空列表
    forbidden_claims: list[str] = Field(default_factory=list)
    # 客服模板字典，默认为空字典，用于根据不同场景自动生成客服话术
    customer_service_templates: dict[str, str] = Field(default_factory=dict)


class SkillConfig(BaseModel):
    # --- 技能配置模型 ---
    # 定义该技能的总体配置，包括基础信息和上述定义的规则
    name: str
    version: str
    owner: str
    enabled: bool
    description: str
    rules: ContentRules


@dataclass(frozen=True)
class ContentPolicyIssue:
    # --- 内容策略问题数据类 ---
    # 在进行内容审计（audit）时，用于记录不符合规则的具体问题
    # code: 错误代码；message: 具体错误信息；blocking: 是否为严重（阻塞性）问题
    code: str
    message: str
    blocking: bool = False


@dataclass(frozen=True)
class OperationContent:
    # --- 运营内容数据类 ---
    # 存储最终生成的完整运营内容
    title: str
    bullets: tuple[str, ...]
    description: str
    keywords: tuple[str, ...]
    customer_service: dict[str, str]

    def as_next_steps(self) -> list[str]:
        # 将当前的运营内容转换为带有特定前缀标识的字符串列表
        # 该格式通常作为工作流中的上下文步骤输出或提供给下游模型使用
        steps = [f"{TITLE_PREFIX}{self.title}"]
        steps.extend(f"{BULLET_PREFIX}{bullet}" for bullet in self.bullets)
        steps.append(f"{DESCRIPTION_PREFIX}{self.description}")
        steps.append(f"{KEYWORDS_PREFIX}{', '.join(self.keywords)}")
        steps.extend(
            f"{CUSTOMER_SERVICE_PREFIX}{name.upper()}: {text}"
            for name, text in sorted(self.customer_service.items())
        )
        return steps

    def as_dict(self) -> dict[str, object]:
        # 将当前的运营内容转换为字典格式，方便 JSON 序列化或供 API 返回
        return {
            "title": self.title,
            "bullets": list(self.bullets),
            "description": self.description,
            "keywords": list(self.keywords),
            "customer_service": dict(self.customer_service),
        }


class OperationContentSkill:
    """Versioned deterministic copy rules for the operations workflow."""
    # --- 运营内容技能主类 ---
    # 负责根据配置中的规则，从产品画像生成标准的运营文案内容，并负责内容的解析和审计。

    def __init__(self, config: SkillConfig) -> None:
        # 初始化方法，如果配置中该技能被禁用，则抛出异常
        if not config.enabled:
            raise ValueError("operation content skill is disabled")
        self.config = config

    @classmethod
    def from_default(cls) -> OperationContentSkill:
        # 类方法：从当前文件同目录下的默认配置文件（skill.yaml）加载并实例化
        return cls.from_yaml(Path(__file__).with_name("skill.yaml"))

    @classmethod
    def from_yaml(cls, path: Path) -> OperationContentSkill:
        # 类方法：读取指定的 YAML 文件，通过 Pydantic 校验后实例化该技能类
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(SkillConfig.model_validate(payload))

    def build(self, *, product: ProductProfile, positioning: str) -> OperationContent:
        # --- 核心方法：构建运营内容 ---
        # 根据产品画像（product）和产品定位（positioning）自动生成各项内容
        rules = self.config.rules

        # 1. 提取并清理关键字段，若缺失则提供默认占位符
        product_name = self._clean(product.name) or self._clean(product.category) or "Product"
        market = self._clean(product.target_market) or "the selected market"
        audience = self._clean(product.target_audience[0]) if product.target_audience else "intended buyers"
        feature = self._first_clean(product.features) or "the supplied product features"
        scenario = self._first_clean(product.use_scenarios) or "the intended use scenario"

        # 2. 构建产品标题：组合产品名称、核心特征、受众和市场，去除重复项并按规则截断长度
        title_parts = self._unique(
            [product_name, feature, f"For {audience}", f"{market} Market"]
        )
        title = self._truncate(" | ".join(title_parts), rules.title.max_chars)

        # 3. 构建产品卖点（bullets）：预定义了一些卖点模板并填入产品信息
        bullet_candidates = [
            f"PRODUCT FOCUS: {self._clean(positioning)}",
            f"KEY FEATURE: {feature}.",
            f"USE SCENARIO: Designed around {scenario}.",
            "BUYER GUIDANCE: Confirm listed specifications, compatibility, and use limits before purchase.",
            "SUPPORT: Contact customer service with the order details for product-specific assistance.",
        ]
        # 根据规则提取所需数量的卖点，清理文本并进行长度截断
        bullets = tuple(
            self._truncate(self._clean(item), rules.bullets.max_chars)
            for item in bullet_candidates[: rules.bullets.count]
        )

        # 4. 构建产品描述：根据规则中定义的模板，格式化填入各项参数，并进行长度限制
        feature_sentence = f"The supplied profile identifies {feature} as a feature."
        scenario_sentence = f"The intended use context is {scenario}."
        description = rules.description.template.format(
            product_name=product_name,
            audience=audience,
            market=market,
            feature_sentence=feature_sentence,
            scenario_sentence=scenario_sentence,
        )
        description = self._truncate(self._clean(description), rules.description.max_chars)

        # 5. 提取关键词：从产品各个属性中收集潜在关键词来源
        keyword_sources = [
            product.name,
            product.category,
            *product.features,
            *product.use_scenarios,
            *product.target_audience,
            product.target_market,
        ]
        # 解析关键词并限制最大数量，如果未提取到任何词，则默认使用产品名称
        keywords = self._keywords(keyword_sources, rules.keywords.max_items)
        if not keywords:
            keywords = (product_name.casefold(),)

        # 6. 生成客服话术：将产品名和市场信息填入配置中定义的所有客服模板中
        format_values = {"product_name": product_name, "market": market}
        customer_service = {
            name: self._clean(template.format(**format_values))
            for name, template in rules.customer_service_templates.items()
        }

        # 返回最终组装好的运营内容对象
        return OperationContent(
            title=title,
            bullets=bullets,
            description=description,
            keywords=keywords,
            customer_service=customer_service,
        )

    def extract(self, steps: list[str]) -> OperationContent | None:
        # --- 核心方法：提取运营内容 ---
        # 遍历由前缀标识的字符串列表，解析并还原出各部分运营内容
        title = ""
        bullets: list[str] = []
        description = ""
        keywords: tuple[str, ...] = ()
        customer_service: dict[str, str] = {}

        for step in steps:
            # 根据前缀匹配，剥离前缀并去掉多余空格，分别存入对应变量
            if step.startswith(TITLE_PREFIX):
                title = step.removeprefix(TITLE_PREFIX).strip()
            elif step.startswith(BULLET_PREFIX):
                bullets.append(step.removeprefix(BULLET_PREFIX).strip())
            elif step.startswith(DESCRIPTION_PREFIX):
                description = step.removeprefix(DESCRIPTION_PREFIX).strip()
            elif step.startswith(KEYWORDS_PREFIX):
                # 关键词通过逗号分隔提取，并去除空串
                keywords = tuple(
                    item.strip() for item in step.removeprefix(KEYWORDS_PREFIX).split(",") if item.strip()
                )
            elif step.startswith(CUSTOMER_SERVICE_PREFIX) and ":" in step:
                # 客服话术包含标识符，格式为 "CUSTOMER_SERVICE_标识: 内容"
                label, text = step.split(":", 1)
                name = label.removeprefix(CUSTOMER_SERVICE_PREFIX).strip().casefold()
                customer_service[name] = text.strip()

        # 如果解析后所有字段都为空，则返回 None
        if not any((title, bullets, description, keywords, customer_service)):
            return None

        return OperationContent(
            title=title,
            bullets=tuple(bullets),
            description=description,
            keywords=keywords,
            customer_service=customer_service,
        )

    def audit(self, content: OperationContent | None) -> list[ContentPolicyIssue]:
        # --- 核心方法：内容审计 ---
        # 检查传入的内容是否符合配置文件中所有的长度、数量及违禁词规则
        if content is None:
            # 如果内容整体为空，返回要求生成所有内容的提示
            return [
                ContentPolicyIssue(
                    code="content_bundle_missing",
                    message="Generate the title, bullets, description, keywords, and customer-service drafts.",
                )
            ]

        rules = self.config.rules
        issues: list[ContentPolicyIssue] = []

        # 检查标题是否存在且长度是否合规
        if not content.title:
            issues.append(ContentPolicyIssue("content_title_missing", "Generate a product title."))
        elif len(content.title) > rules.title.max_chars:
            issues.append(
                ContentPolicyIssue(
                    "content_title_too_long",
                    f"Shorten the title to at most {rules.title.max_chars} characters.",
                )
            )

        # 检查卖点的数量是否与规则要求严格一致
        if len(content.bullets) != rules.bullets.count:
            issues.append(
                ContentPolicyIssue(
                    "content_bullet_count",
                    f"Generate exactly {rules.bullets.count} product bullets.",
                )
            )

        # 检查每个卖点的长度是否超限
        for index, bullet in enumerate(content.bullets):
            if len(bullet) > rules.bullets.max_chars:
                issues.append(
                    ContentPolicyIssue(
                        "content_bullet_too_long",
                        f"Shorten content bullet {index + 1} to at most {rules.bullets.max_chars} characters.",
                    )
                )

        # 检查描述和关键词是否存在，以及关键词数量是否超限
        if not content.description:
            issues.append(ContentPolicyIssue("content_description_missing", "Generate a product description."))
        if not content.keywords:
            issues.append(ContentPolicyIssue("content_keywords_missing", "Generate advertising keywords."))
        elif len(content.keywords) > rules.keywords.max_items:
            issues.append(
                ContentPolicyIssue(
                    "content_keyword_count",
                    f"Limit advertising keywords to {rules.keywords.max_items} items.",
                )
            )

        # 检查是否遗漏了规则中要求生成的某些客服模板
        missing_templates = sorted(
            set(rules.customer_service_templates).difference(content.customer_service)
        )
        if missing_templates:
            issues.append(
                ContentPolicyIssue(
                    "customer_service_template_missing",
                    f"Generate customer-service templates for: {', '.join(missing_templates)}.",
                )
            )

        # 检查违禁词：将所有内容拼接后统一转换为小写进行匹配
        combined = "\n".join(
            [
                content.title,
                *content.bullets,
                content.description,
                *content.keywords,
                *content.customer_service.values(),
            ]
        ).casefold()

        for claim in rules.forbidden_claims:
            if claim.casefold() in combined:
                # 发现违禁词，将其标记为阻塞性（blocking=True）问题
                issues.append(
                    ContentPolicyIssue(
                        "forbidden_marketing_claim",
                        f"Remove the unsupported or prohibited expression: {claim!r}.",
                        blocking=True,
                    )
                )

        return issues

    def _clean(self, value: str) -> str:
        # 内部辅助方法：清理文本
        # 合并多余空格，利用正则忽略大小写地剔除配置中的所有违禁词，并清理两端的特定符号
        text = " ".join(value.split())
        for claim in self.config.rules.forbidden_claims:
            text = re.sub(re.escape(claim), "", text, flags=re.IGNORECASE)
        return " ".join(text.replace("||", "|").split()).strip(" |,;-")

    def _first_clean(self, values: list[str]) -> str:
        # 内部辅助方法：遍历列表，返回第一个清理后非空的有效字符串
        return next((cleaned for value in values if (cleaned := self._clean(value))), "")

    @staticmethod
    def _truncate(value: str, max_chars: int) -> str:
        # 内部静态方法：按指定最大长度截断字符串，如果超长则在末尾追加 "..."
        if len(value) <= max_chars:
            return value
        return f"{value[: max_chars - 3].rstrip()}..."

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        # 内部静态方法：保留字符串列表原有顺序地进行去重（忽略大小写）
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            key = value.casefold()
            if value and key not in seen:
                seen.add(key)
                result.append(value)
        return result

    def _keywords(self, sources: list[str], max_items: int) -> tuple[str, ...]:
        # 内部辅助方法：从指定的源列表中提取关键词
        # 过滤掉预定义的停用词
        stopwords = {"and", "for", "the", "with", "from", "this", "that", "demo"}
        values: list[str] = []
        for source in sources:
            cleaned = self._clean(source)
            # 使用正则表达式匹配英文单词/带连字符词汇，或至少两个字符的中文词汇
            values.extend(re.findall(r"[A-Za-z][A-Za-z0-9-]+|[\u4e00-\u9fff]{2,}", cleaned))

        unique = []
        seen: set[str] = set()
        for value in values:
            normalized = value.casefold()
            # 过滤掉停用词以及重复提取的词汇
            if normalized in stopwords or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(normalized)
            # 达到最大限制后停止提取
            if len(unique) == max_items:
                break
        return tuple(unique)


def content_values(content: OperationContent) -> list[Any]:
    """Return all content values for consumers that need a compact policy scan."""
    # --- 独立辅助函数 ---
    # 提取并展平 OperationContent 中的所有文本内容
    # 方便其他消费者模块进行全局或紧凑的内容策略扫描
    return [
        content.title,
        *content.bullets,
        content.description,
        *content.keywords,
        *content.customer_service.values(),
    ]
