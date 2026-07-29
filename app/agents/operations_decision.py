import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from app.agents.base import BaseScaffoldAgent
from app.agents.contracts import OperationsDecisionAgentInput
from app.agents.model_factory import (
    create_operations_model,
    normalize_evidence_ids,
    normalize_model_data_gaps,
    normalize_text_list,
)
from app.agents.structured_output import invoke_structured
from app.core.config import get_settings
from app.core.enums import AgentStatus, DataMode, DataOrigin, ImplementationStatus
from app.schemas.analysis import OperationPlan
from app.schemas.common import Conclusion, DataGap
from app.skills.operation_content import OperationContentSkill

# 用于匹配文本中带有可选百分号的数字模式（例如 "10"、"5.5%"），以验证模型输出是否在给定上下文中出现过
NUMERIC_SOURCE_PATTERN = r"(?<![A-Za-z0-9_.-])\d+(?:\.\d+)?%?(?![A-Za-z0-9_.-])"
NUMERIC_CLAIM_PATTERN = r"(?<![A-Za-z0-9_.-])\d+(?:\.\d+)?%?"

# OperationsDecisionAgent的系统提示词（System Prompt），规定了模型的角色、输出格式要求、语言规则以及禁止捏造数据等约束
OPERATIONS_SYSTEM_PROMPT = """
You are TradePilot OperationsDecisionAgent. The target is an unlisted new product with no sales or reviews.
All natural-language narrative content must be written in Simplified Chinese.
Keep JSON keys, enum values, brand names, product names, and units in their original form.
Put evidence_id and ASIN only in their dedicated machine fields; never place UUID, evidence_id, parent_asin, or ASIN
inside positioning, strategy fields, conclusions, data gaps, or next_steps.
Your primary deliverable is an actionable launch marketing strategy, not another product-description summary.
Do not state the exact number of peer products or reviews in user-facing prose. Translate descriptive labels and tone
words into Chinese; English is allowed only for immutable brand names, product names, official codes, and units.
Convert the supplied market and user analyses into a specific marketing objective, target segments, value
propositions, pricing strategy, channel strategy, messaging strategy, and evidence-bounded launch actions. Do not
merely repeat feature lists or peer-review findings. Explain how verified findings change positioning, messages,
channels, pricing, or launch gates. Use only the supplied new-product profile and the two evidence-grounded analyses.
Never turn a reasoned_hypothesis into a fact,
never attribute peer reviews to the new product, and never invent evidence IDs or numeric facts.
A reasoned_hypothesis must be derived only from new-product structure, parameters, or usage scenarios. It must not
claim that users "普遍", "高度关注", "反馈", or that reviews "显示/表明" anything; such user/review statements require
peer-review evidence and an evidence-summary conclusion type.
Do not set review-count, rating, conversion, discount, timing, or performance targets unless those exact numbers are
present in the supplied structured inputs. Prefer qualitative launch objectives when the user supplied no target.
When Product background includes tariff decision inputs, reflect their impact on landed cost, margin, pricing buffer,
launch gating, or broker-review requirements instead of treating them as passive reference material.
Return only JSON with status, positioning, marketing_objective, target_segments, value_propositions, pricing_strategy,
channel_strategy, messaging_strategy, launch_actions, conclusions, evidence_ids, data_gaps, and next_steps.
Every factual conclusion must use an evidence_id already present in the supplied analyses or Product background.
Use 同类市场商品, 同类商品评论样本, 同类用户常见关注点, and 新商品上市前需验证事项.
Each conclusion must be {{"conclusion":"...","conclusion_type":"recommendation|evidence_summary|reasoned_hypothesis",
"confidence":0.0,"evidence_ids":[],"data_gaps":[]}}.
"""


class OperationsDecisionAgent(BaseScaffoldAgent[OperationsDecisionAgentInput, OperationPlan]):
    """Build an evidence-aware plan and policy-checked content playbook."""
    # 定义输入和输出的数据模型
    input_model = OperationsDecisionAgentInput
    output_model = OperationPlan

    def __init__(
        self,
        content_skill: OperationContentSkill | None = None,
        model: BaseChatModel | None = None,
    ) -> None:
        """
        初始化运营决策智能体。
        :param content_skill: 运营内容技能（如果未提供，则使用默认实例化）
        :param model: 大语言模型实例
        """
        self.content_skill = content_skill or OperationContentSkill.from_default()
        self.model = model
        # 构建用于 LLM 的聊天提示模板，整合系统提示词和包含多种上下文信息的用户输入
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", OPERATIONS_SYSTEM_PROMPT),
                (
                    "human",
                    "New product:\n{product}\n\nPeer scope:\n{peer_scope}\n\nUser constraints:\n{constraints}\n\n"
                    "Product background:\n{background}\n\nStatistics:\n{statistics}\n\n"
                    "Peer market analysis:\n{market}\n\nPeer user insight:\n{insight}",
                ),
            ]
        )
        super().__init__()

    def _run_stub(self, context: OperationsDecisionAgentInput) -> OperationPlan:
        """
        智能体执行的入口（存根方法）。
        根据上下文数据的模式（DataMode）或数据来源（DataOrigin），
        决定是调用真实大语言模型 (_run_model) 还是使用确定性的模拟方法 (_run_deterministic)。
        """
        if context.product.data_mode is DataMode.REAL or context.product.data_origin is DataOrigin.REAL:
            return self._run_model(context)
        return self._run_deterministic(context)

    def _run_model(self, context: OperationsDecisionAgentInput) -> OperationPlan:
        """
        调用大语言模型执行运营决策分析，并返回结构化的运营计划。
        """
        # 获取或创建默认的运营大语言模型
        model = self.model or create_operations_model()
        normalization_attempt = 0

        def normalize(payload: dict[str, Any]) -> OperationPlan:
            """
            内部函数：在解析 LLM 输出时被调用，用于标准化（清洗和校验）模型返回的数据。
            每次解析重试时 normalization_attempt 递增，以此决定容错级别（例如允许复杂对象）。
            """
            nonlocal normalization_attempt
            normalization_attempt += 1
            return self._postprocess(
                payload,
                context,
                allow_strategy_objects=normalization_attempt > 1,
            )

        # 使用封装的 invoke_structured 方法调用大模型，传入上下文，要求输出 OperationPlan 结构，并挂载 normalize 校验逻辑
        result = invoke_structured(
            prompt=self.prompt,
            model=model,
            values={
                "product": context.product.model_dump_json(indent=2),
                "peer_scope": str(
                    {
                        "peer_group_id": context.peer_group_id,
                        "selected_parent_asins": context.selected_parent_asins,
                    }
                ),
                "constraints": str(context.user_constraints),
                "background": (
                    context.background_context.model_dump_json(indent=2)
                    if context.background_context
                    else "null"
                ),
                "statistics": context.statistics.model_dump_json(indent=2) if context.statistics else "null",
                "market": self._compact_analysis(context.product_market_analysis),
                "insight": self._compact_analysis(context.user_insight),
            },
            output_model=OperationPlan,
            normalize=normalize,
            max_parse_retries=get_settings().model_parse_max_retries,
        )
        # 将模型执行的统计信息（调用次数、Token消耗等）回写到结果中并返回
        return result.value.model_copy(
            update={
                "model_call_count": result.model_call_count,
                "parse_retry_count": result.parse_retry_count,
                "token_usage": result.token_usage,
                "structured_output_parser": result.parser_name,
            }
        )

    def _postprocess(
        self,
        payload: dict[str, Any],
        context: OperationsDecisionAgentInput,
        *,
        allow_strategy_objects: bool = False,
    ) -> OperationPlan:
        """
        后处理方法：对大语言模型返回的原始字典进行清洗、校验与补全。
        主要包括：规范化证据ID、清洗各类策略字段内容、检测并剔除模型捏造的数字指标。
        """
        # 标准化数据缺口信息
        payload = normalize_model_data_gaps(payload, field="operations_decision")
        # 收集上下文中允许的合法证据ID（来自背景信息、市场分析以及用户洞察）
        background_ids = (
            [item.evidence_id for item in context.background_context.evidence]
            if context.background_context is not None
            else []
        )
        allowed_ids = set(
            context.product_market_analysis.evidence_ids
            + context.user_insight.evidence_ids
            + background_ids
        )
        # 将上下文的基础元数据补充到输出负载中
        payload["data_origin"] = context.product.data_origin
        payload["peer_group_id"] = context.peer_group_id
        payload["selected_parent_asins"] = context.selected_parent_asins
        payload["analysis_scopes"] = self._analysis_scopes(context)
        payload["implementation_status"] = ImplementationStatus.PRODUCTION
        payload["scaffold_note"] = ""
        # 清理和校验全局证据ID，移除不在允许列表中的ID，并去重排序
        payload["evidence_ids"] = sorted(
            set(normalize_evidence_ids(payload.get("evidence_ids", []), allowed_ids=allowed_ids))
        )
        # 处理并规范化所有的结论（conclusions）
        conclusions = []
        for conclusion in payload.get("conclusions", []) if isinstance(payload.get("conclusions"), list) else []:
            if not isinstance(conclusion, dict):
                continue
            if not str(conclusion.get("conclusion", "")).strip():
                continue
            # 清洗该结论引用的证据ID
            conclusion["evidence_ids"] = normalize_evidence_ids(
                conclusion.get("evidence_ids", []), allowed_ids=allowed_ids
            )
            # 设定结论默认类型为建议（recommendation），并基于是否有证据支撑赋予默认置信度
            conclusion.setdefault("conclusion_type", "recommendation")
            conclusion.setdefault("confidence", 0.65 if conclusion["evidence_ids"] else 0.35)
            # 若类型为假设，且描述不带有规定的前缀，则主动添加前缀提示
            if conclusion["conclusion_type"] == "reasoned_hypothesis" and not str(
                conclusion.get("conclusion", "")
            ).startswith("待验证假设"):
                conclusion["conclusion"] = (
                    "待验证假设（非用户评论结论、非市场统计事实）："
                    + str(conclusion.get("conclusion", ""))
                )
            # 若结论没有关联的证据ID，也没有说明数据缺口，则强制为其添加一条缺乏证据的数据缺口信息
            if not conclusion["evidence_ids"] and not conclusion.get("data_gaps"):
                conclusion["data_gaps"] = [
                    {
                        "code": "decision_evidence_missing",
                        "field": "operation_plan",
                        "reason": "The recommendation has no valid supplied evidence_id.",
                        "required_for": "evidence-grounded launch decision",
                    }
                ]
            conclusions.append(conclusion)
        payload["conclusions"] = conclusions
        # 判定智能体整体状态：有证据支撑则认为成功，否则标记为证据不足
        payload["status"] = (
            AgentStatus.SUCCEEDED if payload["evidence_ids"] else AgentStatus.INSUFFICIENT_EVIDENCE
        )
        payload.setdefault("data_gaps", [])
        payload["next_steps"] = normalize_text_list(payload.get("next_steps", []))
        # 标准化定位（positioning）和营销目标（marketing_objective）字段，将对象转为清晰的字符串
        payload["positioning"] = self._normalize_positioning(
            payload.get("positioning", ""),
            allow_objects=allow_strategy_objects,
        )
        payload["marketing_objective"] = self._normalize_positioning(
            payload.get("marketing_objective", ""),
            allow_objects=allow_strategy_objects,
        )
        # 标准化其他的各策略列表字段
        strategy_fields = (
            "target_segments",
            "value_propositions",
            "pricing_strategy",
            "channel_strategy",
            "messaging_strategy",
            "launch_actions",
        )
        for field in strategy_fields:
            payload[field] = self._normalize_strategy_list(
                payload.get(field, []),
                allow_objects=allow_strategy_objects,
            )
        # 使用 content_skill 根据商品信息和产品定位，生成额外的运营内容，并补充到下一步行动 (next_steps) 中
        content = self.content_skill.build(product=context.product, positioning=payload["positioning"])
        payload["next_steps"] = [*payload["next_steps"], *content.as_next_steps()]

        # --- 幻觉抑制逻辑：数字和指标校验 ---
        # 收集上下文中允许的所有数字，用于防止模型捏造转化率、目标等数值
        allowed_numbers = self._allowed_numbers(context)
        removed_unsupported_numbers = False
        # 如果产品定位中包含未经支持的数字，将其重置为默认的保守描述
        if self._has_unsupported_numbers(payload["positioning"], allowed_numbers):
            removed_unsupported_numbers = True
            payload["positioning"] = "基于已验证的商品属性和同类市场证据建立差异化定位。"
        # 如果营销目标中包含未经支持的数字，同样重置为默认描述
        if self._has_unsupported_numbers(payload["marketing_objective"], allowed_numbers):
            removed_unsupported_numbers = True
            payload["marketing_objective"] = (
                "围绕已验证的目标客群与价值主张建立首发认知；具体量化目标需由用户确认。"
            )
        # 过滤各策略列表中的幻觉数字项
        for field in strategy_fields:
            accepted_items = [
                item
                for item in payload[field]
                if not self._has_unsupported_numbers(item, allowed_numbers)
            ]
            removed_unsupported_numbers |= len(accepted_items) != len(payload[field])
            payload[field] = accepted_items
        # 过滤结论中的幻觉数字项
        accepted_conclusions = [
            conclusion
            for conclusion in payload["conclusions"]
            if not self._has_unsupported_numbers(
                conclusion.get("conclusion", ""), allowed_numbers
            )
        ]
        removed_unsupported_numbers |= len(accepted_conclusions) != len(payload["conclusions"])
        payload["conclusions"] = accepted_conclusions
        # 过滤下一步行动中的幻觉数字项
        accepted_next_steps = [
            step
            for step in payload["next_steps"]
            if not self._has_unsupported_numbers(step, allowed_numbers)
        ]
        removed_unsupported_numbers |= len(accepted_next_steps) != len(payload["next_steps"])
        payload["next_steps"] = accepted_next_steps
        # 如果存在因为数字不支持而被移除的情况，则增加一条数据缺口说明
        if removed_unsupported_numbers:
            payload["data_gaps"].append(
                {
                    "code": "unsupported_marketing_numeric_target",
                    "field": "operation_plan",
                    "reason": "模型提出了输入证据未支持的量化目标，已从面向用户的策略中移除。",
                    "required_for": "形成可执行的量化营销目标",
                }
            )
        # 最终验证并返回实例化后的运营计划模型
        return OperationPlan.model_validate(payload)

    @staticmethod
    def _allowed_numbers(context: OperationsDecisionAgentInput) -> set[str]:
        """
        从上下文中提取所有合法的数值，以形成白名单，
        用于后续防止大模型捏造不切实际的数据（如虚构转化率、目标量等）。
        """
        # 将商品信息、统计数据和背景上下文转为 JSON 以供正则表达式匹配
        source = {"product": context.product.model_dump(mode="json")}
        if context.statistics is not None:
            source["statistics"] = context.statistics.model_dump(mode="json")
        if context.background_context is not None:
            source["background_context"] = context.background_context.model_dump(mode="json")
        # 从全局信息中提取所有满足条件的数字
        values = set(
            re.findall(
                NUMERIC_SOURCE_PATTERN,
                json.dumps(source, ensure_ascii=False, default=str),
            )
        )
        # 从商品主张信息（排除ID等非业务特征）中提取允许的数字
        product_claim_source = context.product.model_dump(
            mode="json",
            exclude={"product_id", "file_references", "data_gaps"},
        )
        values.update(
            re.findall(
                NUMERIC_CLAIM_PATTERN,
                json.dumps(product_claim_source, ensure_ascii=False, default=str),
            )
        )
        # 对找到的数字尝试进行四舍五入或格式化，以支持多种表现形式的数字校验
        for value in list(values):
            try:
                rounded = Decimal(value.removesuffix("%")).quantize(Decimal("0.01"))
            except InvalidOperation:
                continue
            values.add(format(rounded, "f").rstrip("0").rstrip("."))
        return values

    @staticmethod
    def _sanitize_numeric_text(value: object, allowed_numbers: set[str]) -> str:
        """
        使用合法的数值列表对文本中的数字进行清洗。
        如果文本中的数字不在允许列表里，将被替换为 "待验证数值"。
        """
        text = str(value)

        def replace(match: re.Match[str]) -> str:
            number = match.group(0)
            return number if number in allowed_numbers else "待验证数值"

        return re.sub(NUMERIC_CLAIM_PATTERN, replace, text)

    @staticmethod
    def _has_unsupported_numbers(value: object, allowed_numbers: set[str]) -> bool:
        """
        检测给定的文本或对象中是否包含了未经支持的（幻觉）数字。
        如果存在任一数字不在合法数值列表中，则返回 True。
        """
        return any(
            match.group(0) not in allowed_numbers
            for match in re.finditer(NUMERIC_CLAIM_PATTERN, str(value))
        )

    @staticmethod
    def _normalize_positioning(value: object, *, allow_objects: bool = False) -> str:
        """
        将可能复杂的定位字段（如对象或列表）标准化为单行字符串。
        """
        if isinstance(value, str):
            return value.strip()
        if not allow_objects:
            raise ValueError("OperationPlan strategy summary fields must be strings")
        # 将结构化的策略提取为文本，使用分号拼接
        return "；".join(dict.fromkeys(OperationsDecisionAgent._render_strategy_values(value)))

    @staticmethod
    def _normalize_strategy_list(value: object, *, allow_objects: bool = False) -> list[str]:
        """
        将各种策略（如定价策略、渠道策略等）字段标准化为字符串列表。
        """
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return [item.strip() for item in value if item.strip()]
        if not allow_objects:
            raise ValueError("OperationPlan strategy list fields must contain only strings")
        # 扁平化对象为字符串并去重
        return list(dict.fromkeys(OperationsDecisionAgent._render_strategy_values(value)))

    @staticmethod
    def _render_strategy_values(value: object) -> list[str]:
        """
        递归解析嵌套的策略对象（如列表、字典），并将其转换为一组展平的字符串。
        """
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            return [
                rendered
                for item in value
                for rendered in OperationsDecisionAgent._render_strategy_values(item)
            ]
        if not isinstance(value, dict):
            return []
        rendered = OperationsDecisionAgent._render_strategy_item(value)
        if rendered:
            return [rendered]
        # 遍历字典过滤机器键，提取有意义的业务文本
        return [
            nested
            for key, item in value.items()
            if not OperationsDecisionAgent._is_machine_strategy_key(key)
            for nested in OperationsDecisionAgent._render_strategy_values(item)
        ]

    @staticmethod
    def _render_strategy_item(value: str | dict[str, Any]) -> str:
        """
        提取策略字典中的业务信息，尝试将常见的 title / description 字段组合成
        格式化的 "标题：描述" 字符串，或者合并其他非机器键的文本值。
        """
        if isinstance(value, str):
            return value.strip()
        # 提取候选标题
        title = next(
            (
                str(value[key]).strip()
                for key in ("segment_name", "proposition", "action", "name", "title")
                if value.get(key)
            ),
            "",
        )
        # 提取候选描述
        description = next(
            (
                str(value[key]).strip()
                for key in ("description", "rationale", "strategy", "message", "reason")
                if value.get(key)
            ),
            "",
        )
        # 判断标题是否包含中文字符
        has_chinese_title = any("\u4e00" <= character <= "\u9fff" for character in title)
        if description:
            return f"{title}：{description}" if title and has_chinese_title else description
        # 如果没有典型的标题/描述对，提取所有有效的标量值合并
        parts = [
            str(item).strip()
            for key, item in value.items()
            if not OperationsDecisionAgent._is_machine_strategy_key(key)
            and isinstance(item, (str, int, float))
            and str(item).strip()
        ]
        return "；".join(dict.fromkeys(parts))

    @staticmethod
    def _is_machine_strategy_key(key: str) -> bool:
        """
        判断字典的键是否是用于机器标识或元数据的字段（如优先级、类型、置信度、ID等），
        这类字段不应作为人类可读文本展示给用户。
        """
        normalized = key.casefold()
        return (
            normalized in {"priority", "type", "confidence", "parent_asin", "asin"}
            or normalized.endswith("_id")
            or normalized.endswith("_ids")
        )

    @staticmethod
    def _compact_analysis(value: Any) -> str:
        """
        压缩分析对象：移除如 scaffold_note、data_gaps 等不需要发送给大模型的冗余字段，
        以节省 Token 消耗并降低干扰。
        """
        payload = value.model_dump(mode="json")
        return str(
            {
                key: payload.get(key)
                for key in payload
                if key not in {"scaffold_note", "selected_parent_asins", "data_gaps"}
            }
        )

    def _run_deterministic(self, context: OperationsDecisionAgentInput) -> OperationPlan:
        """
        确定性执行逻辑（Fallback/Mock模式）：
        当上下文中没有真实数据或模型执行被跳过时使用。
        根据已知证据和商品信息，组装一个结构化的保底计划。
        """
        # 合并并汇总上下文中所有相关的证据ID和数据缺口
        core_evidence_ids = sorted(
            set(context.product_market_analysis.evidence_ids + context.user_insight.evidence_ids)
        )
        background_evidence_ids = (
            [item.evidence_id for item in context.background_context.evidence]
            if context.background_context is not None
            else []
        )
        evidence_ids = sorted(set([*core_evidence_ids, *background_evidence_ids]))
        data_gaps = self._merge_gaps(
            context.product.data_gaps,
            context.product_market_analysis.data_gaps,
            context.user_insight.data_gaps,
        )
        # 如果没有核心证据ID，说明缺乏分析依据，人为添加一条严重的数据缺口
        if not core_evidence_ids:
            data_gaps = self._merge_gaps(
                data_gaps,
                [
                    DataGap(
                        code="decision_evidence_missing",
                        field="operation_plan",
                        reason="No product-market or user-insight evidence is available for the decision.",
                        required_for="evidence-grounded positioning and marketing claims",
                    )
                ],
            )

        product = context.product
        market = product.target_market or "the selected target market"
        audience = product.target_audience[0] if product.target_audience else "the intended buyer segment"
        value_focus = product.features[0] if product.features else "verified product attributes"
        # 组装基础产品定位文案
        evidence_note = (
            "Use the cited product and user evidence as the validation boundary."
            if core_evidence_ids
            else "Treat this as a profile-led hypothesis until product and user evidence is supplied."
        )
        positioning = (
            f"Position {product.name} for {audience} in {market} around {value_focus}. {evidence_note}"
        )

        # 构建最终结论列表
        conclusions = [
            Conclusion(
                conclusion=positioning,
                conclusion_type="recommendation",
                confidence=0.72 if core_evidence_ids else 0.35,
                evidence_ids=core_evidence_ids,
                data_gaps=[] if core_evidence_ids else data_gaps,
            )
        ]
        # 附加由用户提供的市场或价格目标结论
        if product.target_market:
            conclusions.append(
                Conclusion(
                    conclusion=f"The user-selected target market is {product.target_market}.",
                    conclusion_type="user_input",
                    confidence=1.0,
                )
            )
        if product.target_price is not None:
            currency = f" {product.target_currency}" if product.target_currency else ""
            conclusions.append(
                Conclusion(
                    conclusion=f"The user target price is {product.target_price}{currency}.",
                    conclusion_type="user_input",
                    confidence=1.0,
                )
            )
        # 若存在数据缺口，在结论中明确提出其限制性
        if data_gaps:
            conclusions.append(
                Conclusion(
                    conclusion=(
                        "Market, pricing, and audience claims remain limited to the supplied profile and cited "
                        "evidence; unresolved gaps must be shown in the final report."
                    ),
                    conclusion_type="data_limitation",
                    confidence=1.0,
                    data_gaps=data_gaps,
                )
            )

        # 结合关税及背景决策信息，补充相应的结论与待执行任务
        tariff_brief = ""
        tariff_actions: list[str] = []
        if context.background_context is not None and context.background_context.decision_inputs:
            tariff_brief = str(
                context.background_context.decision_inputs.get("agent_decision_brief")
                or context.background_context.decision_inputs.get("tariff_summary")
                or ""
            ).strip()
            tariff_actions = [
                str(item).strip()
                for item in context.background_context.decision_inputs.get("tariff_recommended_actions", [])
                if str(item).strip()
            ]
        if tariff_brief:
            conclusions.append(
                Conclusion(
                    conclusion=f"Tariff decision input: {tariff_brief}",
                    conclusion_type="recommendation",
                    confidence=0.8 if background_evidence_ids else 0.5,
                    evidence_ids=background_evidence_ids,
                )
            )

        # 调用技能生成内容并组合出未来的建议行动步骤
        content = self.content_skill.build(product=product, positioning=positioning)
        next_steps = [
            "ACTION: Validate the proposed positioning against current marketplace evidence before launch.",
            "ACTION: Confirm every product specification and compatibility statement before publishing.",
            "ACTION: Add structured competitor prices and review statistics before making numeric claims.",
            *[f"ACTION: {item}" for item in tariff_actions],
            *content.as_next_steps(),
        ]

        # 计算并整合智能体状态
        statuses = {
            context.product_market_analysis.status,
            context.user_insight.status,
        }
        if AgentStatus.FAILED in statuses:
            status = AgentStatus.FAILED
        elif core_evidence_ids:
            status = AgentStatus.SUCCEEDED
        else:
            status = AgentStatus.INSUFFICIENT_EVIDENCE

        # 返回构建好的 OperationPlan 模拟数据
        return OperationPlan(
            status=status,
            data_origin=product.data_origin,
            conclusions=conclusions,
            evidence_ids=evidence_ids,
            data_gaps=data_gaps,
            positioning=positioning,
            next_steps=next_steps,
            peer_group_id=context.peer_group_id,
            selected_parent_asins=context.selected_parent_asins,
            analysis_scopes=self._analysis_scopes(context),
            scaffold_note=(
                "Deterministic Demo operations rules v1 are active; model-backed optimization and real market "
                "execution remain outside the scaffold boundary."
            ),
        )

    @staticmethod
    def _analysis_scopes(context: OperationsDecisionAgentInput) -> dict[str, object]:
        """
        从输入上下文中提取用于前置分析（市场分析和用户洞察）的作用域元数据
        （如竞品组ID，被选择的ASIN）。
        """
        return {
            "product_market_agent": {
                "peer_group_id": context.product_market_analysis.peer_group_id,
                "selected_parent_asins": context.product_market_analysis.selected_parent_asins,
            },
            "user_insight_agent": {
                "peer_group_id": context.user_insight.peer_group_id,
                "selected_parent_asins": context.user_insight.selected_parent_asins,
            },
        }

    @staticmethod
    def _merge_gaps(*groups: list[DataGap]) -> list[DataGap]:
        """
        合并多个来源的 DataGap（数据缺口）列表，并去重。
        去重规则基于 code, field, reason 和 required_for。
        """
        result: list[DataGap] = []
        seen: set[tuple[str, str, str, str | None]] = set()
        for gap in (item for group in groups for item in group):
            key = (gap.code, gap.field, gap.reason, gap.required_for)
            if key not in seen:
                seen.add(key)
                result.append(gap)
        return result
