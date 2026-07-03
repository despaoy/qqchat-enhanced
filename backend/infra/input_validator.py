"""
输入验证模块 - 全面的API输入验证和安全检测

提供集中化的输入验证规则，包括：
- 字符串长度限制
- SQL注入检测
- XSS检测
- 路径遍历检测
- 命令注入检测
- 特殊字符过滤
- 类型和范围验证

使用方式：
    from input_validator import InputValidator, validate_input, MESSAGE_SCHEMA

    # 直接验证
    is_valid, errors = InputValidator.validate(data, MESSAGE_SCHEMA)

    # 装饰器验证（FastAPI路由）
    @router.post("/messages")
    @validate_input(MESSAGE_SCHEMA)
    async def create_message(request: Request):
        ...
"""

from __future__ import annotations

import functools
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 异常类
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """输入验证失败时抛出的异常。

    Attributes:
        errors: 验证错误详情列表，每项包含字段名和错误描述
    """

    def __init__(self, errors: list[dict[str, str]]) -> None:
        self.errors = errors
        message = "; ".join(f"{e['field']}: {e['message']}" for e in errors)
        super().__init__(f"Validation failed: {message}")

    def to_dict(self) -> dict[str, Any]:
        """将验证错误转换为字典格式，便于API响应。"""
        return {
            "detail": "Validation failed",
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# 字段类型枚举
# ---------------------------------------------------------------------------

class FieldType(Enum):
    """支持的字段类型。"""
    STRING = "str"
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    LIST = "list"
    DICT = "dict"


# ---------------------------------------------------------------------------
# 字段规则定义
# ---------------------------------------------------------------------------

@dataclass
class FieldRule:
    """单个字段的验证规则。

    Attributes:
        field_type: 字段期望类型
        required: 是否必填
        min_length: 字符串最小长度
        max_length: 字符串最大长度
        min_value: 数值最小值
        max_value: 数值最大值
        pattern: 正则匹配模式
        allowed_values: 允许的枚举值列表
        check_sql_injection: 是否检测SQL注入
        check_xss: 是否检测XSS
        check_path_traversal: 是否检测路径遍历
        check_command_injection: 是否检测命令注入
        sanitize: 是否自动清理控制字符
        custom_validator: 自定义验证函数 (value) -> Optional[str]，返回错误消息或None
    """

    field_type: FieldType = FieldType.STRING
    required: bool = True
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None
    allowed_values: Optional[list[Any]] = None
    check_sql_injection: bool = False
    check_xss: bool = False
    check_path_traversal: bool = False
    check_command_injection: bool = False
    sanitize: bool = True
    custom_validator: Optional[Callable[[Any], Optional[str]]] = None


@dataclass
class Schema:
    """验证模式，定义一组字段的规则。

    Attributes:
        fields: 字段名到规则的映射
        allow_extra: 是否允许模式中未定义的额外字段
    """

    fields: dict[str, FieldRule] = field(default_factory=dict)
    allow_extra: bool = False


# ---------------------------------------------------------------------------
# 安全检测模式
# ---------------------------------------------------------------------------

# SQL注入模式
_SQL_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(\b|\')(?:OR|AND)\s+\d+\s*=\s*\d+", re.IGNORECASE),
    re.compile(r"\bUNION\b\s+(?:ALL\s+)?\bSELECT\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+(?:TABLE|DATABASE|INDEX)", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
    re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE),
    re.compile(r"\bUPDATE\s+\w+\s+SET\b", re.IGNORECASE),
    re.compile(r";\s*(?:SELECT|DROP|DELETE|INSERT|UPDATE|ALTER|CREATE)\b", re.IGNORECASE),
    re.compile(r"--\s*$", re.IGNORECASE),
    re.compile(r"/\*.*\*/", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bEXEC(?:UTE)?\b", re.IGNORECASE),
    re.compile(r"\bXP_\(CMDSHELL\)", re.IGNORECASE),
    re.compile(r"'\s*OR\s+'", re.IGNORECASE),
    re.compile(r"\bWAITFOR\s+DELAY\b", re.IGNORECASE),
    re.compile(r"\bBENCHMARK\s*\(", re.IGNORECASE),
    re.compile(r"\bSLEEP\s*\(", re.IGNORECASE),
]

# XSS检测模式
_XSS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"<\s*script", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"\bon\w+\s*=", re.IGNORECASE),  # onerror=, onload=, etc.
    re.compile(r"<\s*iframe", re.IGNORECASE),
    re.compile(r"<\s*object", re.IGNORECASE),
    re.compile(r"<\s*embed", re.IGNORECASE),
    re.compile(r"<\s*form", re.IGNORECASE),
    re.compile(r"eval\s*\(", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),
    re.compile(r"vbscript\s*:", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
]

# 路径遍历模式
_PATH_TRAVERSAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\.\./"),
    re.compile(r"\.\.\\"),
    re.compile(r"\.\.%2[fF]"),
    re.compile(r"%2[eE]%2[eE]/"),
    re.compile(r"%2[eE]%2[eE]\\"),
    re.compile(r"\.\.%5[cC]"),
    re.compile(r"~/" ),
    re.compile(r"~\\"),
]

# 命令注入模式
_COMMAND_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r";\s*rm\b", re.IGNORECASE),
    re.compile(r";\s*del\b", re.IGNORECASE),
    re.compile(r"\|\s*cat\b", re.IGNORECASE),
    re.compile(r"\|\s*sh\b", re.IGNORECASE),
    re.compile(r"\|\s*bash\b", re.IGNORECASE),
    re.compile(r"&&\s*del\b", re.IGNORECASE),
    re.compile(r"&&\s*rm\b", re.IGNORECASE),
    re.compile(r"`[^`]+`"),
    re.compile(r"\$\([^)]+\)"),
    re.compile(r"\b(?:wget|curl)\s+", re.IGNORECASE),
    re.compile(r"\b(?:chmod|chown|chgrp)\s+", re.IGNORECASE),
    re.compile(r"\bnc\s+-", re.IGNORECASE),
    re.compile(r">\s*/dev/", re.IGNORECASE),
]

# 控制字符模式（\x00-\x1f，排除\t\n\r）
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


# ---------------------------------------------------------------------------
# 预定义Schema
# ---------------------------------------------------------------------------

MESSAGE_SCHEMA = Schema(
    fields={
        "message": FieldRule(
            field_type=FieldType.STRING,
            required=True,
            min_length=1,
            max_length=10000,
            check_sql_injection=True,
            check_xss=True,
            check_command_injection=True,
            sanitize=True,
        ),
        "title": FieldRule(
            field_type=FieldType.STRING,
            required=False,
            max_length=200,
            check_sql_injection=True,
            check_xss=True,
            sanitize=True,
        ),
        "limit": FieldRule(
            field_type=FieldType.INTEGER,
            required=False,
            min_value=1,
            max_value=1000,
        ),
        "offset": FieldRule(
            field_type=FieldType.INTEGER,
            required=False,
            min_value=0,
        ),
    },
    allow_extra=True,
)

KNOWLEDGE_DOCUMENT_SCHEMA = Schema(
    fields={
        "title": FieldRule(
            field_type=FieldType.STRING,
            required=True,
            min_length=1,
            max_length=200,
            check_sql_injection=True,
            check_xss=True,
            sanitize=True,
        ),
        "content": FieldRule(
            field_type=FieldType.STRING,
            required=True,
            min_length=1,
            max_length=50000,
            check_sql_injection=True,
            check_xss=True,
            sanitize=True,
        ),
        "category": FieldRule(
            field_type=FieldType.STRING,
            required=False,
            max_length=100,
            check_sql_injection=True,
            sanitize=True,
        ),
        "tags": FieldRule(
            field_type=FieldType.LIST,
            required=False,
        ),
    },
    allow_extra=True,
)

KNOWLEDGE_SEARCH_SCHEMA = Schema(
    fields={
        "query": FieldRule(
            field_type=FieldType.STRING,
            required=True,
            min_length=1,
            max_length=1000,
            check_sql_injection=True,
            check_xss=True,
            sanitize=True,
        ),
        "top_k": FieldRule(
            field_type=FieldType.INTEGER,
            required=False,
            min_value=1,
            max_value=50,
        ),
    },
    allow_extra=True,
)

# Backward-compatible name for existing imports. Search requests need query;
# document create/update endpoints must use KNOWLEDGE_DOCUMENT_SCHEMA explicitly.
KNOWLEDGE_SCHEMA = KNOWLEDGE_SEARCH_SCHEMA
TRAINING_SCHEMA = Schema(
    fields={
        "lora_name": FieldRule(
            field_type=FieldType.STRING,
            required=True,
            min_length=1,
            max_length=200,
            check_sql_injection=True,
            check_path_traversal=True,
            sanitize=True,
        ),
        "dataset_name": FieldRule(
            field_type=FieldType.STRING,
            required=True,
            min_length=1,
            max_length=100,
            check_sql_injection=True,
            check_path_traversal=True,
            sanitize=True,
        ),
        "model_type": FieldRule(
            field_type=FieldType.STRING,
            required=True,
            min_length=1,
            max_length=200,
            check_sql_injection=True,
            check_path_traversal=True,
            sanitize=True,
        ),
        "style": FieldRule(
            field_type=FieldType.STRING,
            required=False,
            max_length=100,
            sanitize=True,
        ),
        "epochs": FieldRule(
            field_type=FieldType.INTEGER,
            required=False,
            min_value=1,
            max_value=100,
        ),
        "batch_size": FieldRule(
            field_type=FieldType.INTEGER,
            required=False,
            min_value=1,
            max_value=32,
        ),
        "learning_rate": FieldRule(
            field_type=FieldType.FLOAT,
            required=False,
            min_value=1e-7,
            max_value=1.0,
        ),
        "lora_rank": FieldRule(
            field_type=FieldType.INTEGER,
            required=False,
            min_value=1,
            max_value=256,
        ),
    },
    allow_extra=True,
)

CONFIG_SCHEMA = Schema(
    fields={
        "key": FieldRule(
            field_type=FieldType.STRING,
            required=True,
            min_length=1,
            max_length=100,
            check_sql_injection=True,
            sanitize=True,
        ),
        "value": FieldRule(
            field_type=FieldType.STRING,
            required=True,
            max_length=10000,
            check_sql_injection=True,
            check_xss=True,
            sanitize=True,
        ),
        "provider": FieldRule(
            field_type=FieldType.STRING,
            required=False,
            max_length=50,
            allowed_values=["local", "openai", "zhipu", "deepseek", "ollama"],
        ),
    },
    allow_extra=True,
)


# ---------------------------------------------------------------------------
# 核心验证器
# ---------------------------------------------------------------------------

class InputValidator:
    """集中管理所有API输入验证规则。

    提供静态方法用于验证数据、检测安全威胁和清理输入字符串。
    所有验证方法均为无状态的，可安全并发调用。
    """

    @staticmethod
    def validate(data: dict[str, Any], schema: Schema) -> tuple[bool, list[dict[str, str]]]:
        """根据给定的Schema验证数据。

        Args:
            data: 待验证的数据字典
            schema: 验证模式定义

        Returns:
            (is_valid, errors) 元组：
            - is_valid: 验证是否通过
            - errors: 错误列表，每项包含 field 和 message
        """
        errors: list[dict[str, str]] = []

        if not isinstance(data, dict):
            errors.append({"field": "_root", "message": "输入数据必须是字典类型"})
            return False, errors

        # 检查必填字段
        for field_name, rule in schema.fields.items():
            if rule.required and field_name not in data:
                errors.append({"field": field_name, "message": "此字段为必填项"})
                continue

        # 验证每个存在的字段
        for field_name, value in data.items():
            if field_name not in schema.fields:
                if not schema.allow_extra:
                    errors.append({"field": field_name, "message": "未定义的字段"})
                continue

            rule = schema.fields[field_name]
            field_errors = InputValidator._validate_field(field_name, value, rule)
            errors.extend(field_errors)

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning("输入验证失败: %s", errors)
        return is_valid, errors

    @staticmethod
    def _validate_field(field_name: str, value: Any, rule: FieldRule) -> list[dict[str, str]]:
        """验证单个字段。

        Args:
            field_name: 字段名称
            value: 字段值
            rule: 字段验证规则

        Returns:
            错误列表
        """
        errors: list[dict[str, str]] = []

        # 允许非必填字段为None
        if value is None:
            if rule.required:
                errors.append({"field": field_name, "message": "此字段不能为None"})
            return errors

        # 类型验证
        type_error = InputValidator._validate_type(field_name, value, rule.field_type)
        if type_error:
            errors.append(type_error)
            return errors  # 类型不对，后续验证无意义

        # 字符串类型验证
        if rule.field_type == FieldType.STRING and isinstance(value, str):
            str_errors = InputValidator._validate_string_field(field_name, value, rule)
            errors.extend(str_errors)

        # 数值类型验证
        if rule.field_type in (FieldType.INTEGER, FieldType.FLOAT):
            num_errors = InputValidator._validate_numeric_field(field_name, value, rule)
            errors.extend(num_errors)

        # 列表类型验证
        if rule.field_type == FieldType.LIST and isinstance(value, list):
            list_errors = InputValidator._validate_list_field(field_name, value, rule)
            errors.extend(list_errors)

        # 枚举值验证
        if rule.allowed_values is not None and value not in rule.allowed_values:
            errors.append({
                "field": field_name,
                "message": f"值不在允许范围内，允许值: {rule.allowed_values}",
            })

        # 正则模式验证
        if rule.pattern is not None and isinstance(value, str):
            if not re.match(rule.pattern, value):
                errors.append({
                    "field": field_name,
                    "message": f"值不匹配要求的格式",
                })

        # 自定义验证器
        if rule.custom_validator is not None:
            try:
                custom_error = rule.custom_validator(value)
                if custom_error:
                    errors.append({"field": field_name, "message": custom_error})
            except Exception as exc:
                logger.error("自定义验证器异常: %s", exc)
                errors.append({"field": field_name, "message": "自定义验证失败"})

        return errors

    @staticmethod
    def _validate_type(field_name: str, value: Any, expected_type: FieldType) -> Optional[dict[str, str]]:
        """验证字段类型。"""
        type_checks: dict[FieldType, tuple[type, ...]] = {
            FieldType.STRING: (str,),
            FieldType.INTEGER: (int,),  # 注意：bool是int的子类，需要额外排除
            FieldType.FLOAT: (int, float),
            FieldType.BOOLEAN: (bool,),
            FieldType.LIST: (list,),
            FieldType.DICT: (dict,),
        }

        expected = type_checks.get(expected_type)
        if expected is None:
            return None

        # 特殊处理：bool不是int
        if expected_type == FieldType.INTEGER and isinstance(value, bool):
            return {"field": field_name, "message": f"期望类型 {expected_type.value}，实际为 bool"}

        if not isinstance(value, expected):
            actual_type = type(value).__name__
            return {"field": field_name, "message": f"期望类型 {expected_type.value}，实际为 {actual_type}"}

        return None

    @staticmethod
    def _validate_string_field(field_name: str, value: str, rule: FieldRule) -> list[dict[str, str]]:
        """验证字符串类型字段的各项规则。"""
        errors: list[dict[str, str]] = []

        # 长度验证
        if rule.min_length is not None and len(value) < rule.min_length:
            errors.append({
                "field": field_name,
                "message": f"长度不能少于 {rule.min_length} 个字符",
            })
        if rule.max_length is not None and len(value) > rule.max_length:
            errors.append({
                "field": field_name,
                "message": f"长度不能超过 {rule.max_length} 个字符",
            })

        # 安全检测
        if rule.check_sql_injection:
            sql_error = InputValidator._check_sql_injection(field_name, value)
            if sql_error:
                errors.append(sql_error)

        if rule.check_xss:
            xss_error = InputValidator._check_xss(field_name, value)
            if xss_error:
                errors.append(xss_error)

        if rule.check_path_traversal:
            path_error = InputValidator._check_path_traversal(field_name, value)
            if path_error:
                errors.append(path_error)

        if rule.check_command_injection:
            cmd_error = InputValidator._check_command_injection(field_name, value)
            if cmd_error:
                errors.append(cmd_error)

        # 控制字符检测
        if rule.sanitize and _CONTROL_CHAR_PATTERN.search(value):
            errors.append({
                "field": field_name,
                "message": "包含非法控制字符",
            })

        return errors

    @staticmethod
    def _validate_numeric_field(field_name: str, value: Any, rule: FieldRule) -> list[dict[str, str]]:
        """验证数值类型字段。"""
        errors: list[dict[str, str]] = []

        if rule.min_value is not None and value < rule.min_value:
            errors.append({
                "field": field_name,
                "message": f"值不能小于 {rule.min_value}",
            })
        if rule.max_value is not None and value > rule.max_value:
            errors.append({
                "field": field_name,
                "message": f"值不能大于 {rule.max_value}",
            })

        return errors

    @staticmethod
    def _validate_list_field(field_name: str, value: list, rule: FieldRule) -> list[dict[str, str]]:
        """验证列表类型字段。"""
        errors: list[dict[str, str]] = []

        if rule.min_length is not None and len(value) < rule.min_length:
            errors.append({
                "field": field_name,
                "message": f"列表元素数量不能少于 {rule.min_length}",
            })
        if rule.max_length is not None and len(value) > rule.max_length:
            errors.append({
                "field": field_name,
                "message": f"列表元素数量不能超过 {rule.max_length}",
            })

        return errors

    # -----------------------------------------------------------------------
    # 安全检测方法
    # -----------------------------------------------------------------------

    @staticmethod
    def _check_sql_injection(field_name: str, value: str) -> Optional[dict[str, str]]:
        """检测SQL注入模式。"""
        for pattern in _SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                logger.warning("SQL注入检测触发: field=%s, pattern=%s", field_name, pattern.pattern)
                return {
                    "field": field_name,
                    "message": "输入包含潜在的SQL注入内容",
                }
        return None

    @staticmethod
    def _check_xss(field_name: str, value: str) -> Optional[dict[str, str]]:
        """检测XSS攻击模式。"""
        for pattern in _XSS_PATTERNS:
            if pattern.search(value):
                logger.warning("XSS检测触发: field=%s, pattern=%s", field_name, pattern.pattern)
                return {
                    "field": field_name,
                    "message": "输入包含潜在的XSS攻击内容",
                }
        return None

    @staticmethod
    def _check_path_traversal(field_name: str, value: str) -> Optional[dict[str, str]]:
        """检测路径遍历模式。"""
        for pattern in _PATH_TRAVERSAL_PATTERNS:
            if pattern.search(value):
                logger.warning("路径遍历检测触发: field=%s, pattern=%s", field_name, pattern.pattern)
                return {
                    "field": field_name,
                    "message": "输入包含潜在的路径遍历内容",
                }
        return None

    @staticmethod
    def _check_command_injection(field_name: str, value: str) -> Optional[dict[str, str]]:
        """检测命令注入模式。"""
        for pattern in _COMMAND_INJECTION_PATTERNS:
            if pattern.search(value):
                logger.warning("命令注入检测触发: field=%s, pattern=%s", field_name, pattern.pattern)
                return {
                    "field": field_name,
                    "message": "输入包含潜在的命令注入内容",
                }
        return None


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def sanitize_string(input_str: str) -> str:
    """清理输入字符串，移除控制字符和危险内容。

    处理步骤：
    1. 移除控制字符（保留\\t, \\n, \\r）
    2. HTML实体编码危险字符
    3. 去除首尾空白

    Args:
        input_str: 待清理的字符串

    Returns:
        清理后的安全字符串
    """
    if not isinstance(input_str, str):
        return ""

    # 移除控制字符（保留 \t \n \r）
    cleaned = _CONTROL_CHAR_PATTERN.sub("", input_str)

    # HTML实体编码
    html_escape_map: dict[str, str] = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
    }
    for char, entity in html_escape_map.items():
        cleaned = cleaned.replace(char, entity)

    # 去除首尾空白
    cleaned = cleaned.strip()

    return cleaned


# ---------------------------------------------------------------------------
# FastAPI装饰器
# ---------------------------------------------------------------------------

def validate_input(schema: Schema) -> Callable:
    """FastAPI路由装饰器，在请求处理前验证输入数据。

    从请求体中读取JSON数据，根据给定的Schema进行验证。
    验证失败时返回HTTP 422响应。

    Args:
        schema: 验证模式

    Returns:
        装饰器函数

    使用示例:
        @router.post("/messages")
        @validate_input(MESSAGE_SCHEMA)
        async def create_message(request: Request):
            data = request.state.validated_data
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 尝试从参数中找到Request对象
            request = None
            for arg in args:
                # FastAPI的Request对象
                if hasattr(arg, "json") and hasattr(arg, "state"):
                    request = arg
                    break

            if request is None:
                # 从kwargs中查找
                request = kwargs.get("request")

            if request is None:
                logger.error("validate_input装饰器无法找到Request对象")
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=500,
                    content={"detail": "内部错误：无法获取请求对象"},
                )

            # 读取请求体
            try:
                body = await request.json()
            except Exception as exc:
                logger.warning("请求体JSON解析失败: %s", exc)
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=400,
                    content={"detail": "无效的JSON格式"},
                )

            # 执行验证
            is_valid, errors = InputValidator.validate(body, schema)
            if not is_valid:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=422,
                    content={
                        "detail": "Validation failed",
                        "errors": errors,
                    },
                )

            # 将验证通过的数据存储到request.state
            request.state.validated_data = body

            return await func(*args, **kwargs)

        return wrapper

    return decorator
