# 导入抽象基类模块，用于定义具有抽象方法的基类
from abc import ABC, abstractmethod

# 导入 LangChain 核心模块中的 Runnable 组件，用于构建可执行的序列链 (LCEL)
from langchain_core.runnables import RunnableLambda, RunnableSequence
# 导入 Pydantic 的 BaseModel，用于输入输出数据的结构化定义与验证
from pydantic import BaseModel


# 定义一个泛型基类 BaseScaffoldAgent，继承自 ABC（抽象基类）
# InputT 和 OutputT 是泛型类型变量，它们都限定为 Pydantic 的 BaseModel 的子类
class BaseScaffoldAgent[InputT: BaseModel, OutputT: BaseModel](ABC):
    # 定义类属性，用于在子类中显式指定输入和输出的具体 Pydantic 模型类型
    input_model: type[InputT]
    output_model: type[OutputT]

    def __init__(self) -> None:
        # 初始化方法，构建一个 LangChain 的 RunnableSequence（执行链）
        # 该链条通过管道操作符 (|) 将三个步骤串联起来，依次为：
        # 1. 验证并转换输入数据
        # 2. 执行具体的业务逻辑 (由子类实现)
        # 3. 验证并转换输出数据
        self.chain: RunnableSequence = (
            RunnableLambda(self._validate_input)
            | RunnableLambda(self._run_stub)
            | RunnableLambda(self._validate_output)
        )

    def run(self, context: InputT) -> OutputT:
        # 对外暴露的主执行方法，接收符合 InputT 类型或字典的上下文对象
        # 调用内部构建的执行链来处理数据，并返回类型为 OutputT 的结果
        return self.chain.invoke(context)

    def _validate_input(self, value: InputT | dict[str, object]) -> InputT:
        # 内部输入验证方法：
        # 利用类属性 input_model 提供的 Pydantic 模型，对传入的 value 进行验证和反序列化
        # 无论传入的是字典还是对象，都能确保返回一个合法的 InputT 实例
        return self.input_model.model_validate(value)

    @abstractmethod
    def _run_stub(self, context: InputT) -> OutputT | dict[str, object]:
        """
        在共享的 LCEL (LangChain Expression Language) 验证链内部运行具体的业务逻辑实现。

        这是一个抽象方法，所有继承 BaseScaffoldAgent 的子类都必须实现此方法。
        子类在此处编写核心的 Agent 处理逻辑。
        """

    def _validate_output(self, value: OutputT | dict[str, object]) -> OutputT:
        # 内部输出验证方法：
        # 利用类属性 output_model 提供的 Pydantic 模型，对 _run_stub 返回的结果进行验证
        # 确保最终返回给调用方的数据严格符合 OutputT 的结构定义
        return self.output_model.model_validate(value)
