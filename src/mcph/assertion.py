"""Assertion engine for evaluating ASSERT nodes against JSON-RPC responses."""

from __future__ import annotations

import re
from typing import Any, NoReturn

from jsonpath_ng.ext import parse as parse_jsonpath  # type: ignore[import-untyped]

from mcph.ast import Assert, FuzzyType, TemplateString


class AssertionError(Exception):
    """Raised when an assertion fails, with details about expected vs actual."""

    def __init__(self, message: str, query: str, expected: Any, actual: Any) -> None:
        self.query = query
        self.expected = expected
        self.actual = actual
        super().__init__(message)


class AssertionEngine:
    """Evaluate assertion nodes against full JSON-RPC response envelopes."""

    def evaluate(self, assertion: Assert, response: dict[str, Any]) -> bool:
        """Evaluate a single assertion against a response dict."""
        if assertion.query == "STATUS":
            return self._evaluate_status(assertion, response)

        values = self._resolve_query(assertion.query, response)

        if assertion.predicate == "EXISTS":
            return self._evaluate_exists(assertion, values)
        if assertion.predicate == "COUNT":
            return self._evaluate_count(assertion, values)

        actual_exists = len(values) > 0
        actual = self._coerce_actual(values)
        passed = self._evaluate_scalar_predicate(
            predicate=assertion.predicate,
            actual=actual,
            expected=assertion.expected_value,
            actual_exists=actual_exists,
        )
        if passed:
            return True

        self._fail(
            assertion=assertion,
            expected_text=f"{assertion.query} {assertion.predicate} "
            f"{self._value_to_text(assertion.expected_value)}",
            actual_text=f"{self._value_to_text(actual)}",
            actual=actual,
        )
        return False

    def _evaluate_status(self, assertion: Assert, response: dict[str, Any]) -> bool:
        expected = self._to_int(assertion.expected_value)
        if expected is None:
            self._fail(
                assertion=assertion,
                expected_text="STATUS expected to compare against an integer code",
                actual_text=f"got {self._value_to_text(assertion.expected_value)}",
                actual=None,
            )

        has_result = "result" in response and "error" not in response
        error_code = self._extract_error_code(response)
        actual_status: int | None = 200 if has_result else error_code

        if assertion.predicate == "==":
            passed = has_result if expected == 200 else error_code == expected
        else:
            passed = self._evaluate_numeric_predicate(assertion.predicate, actual_status, expected)

        if passed:
            return True

        if expected == 200:
            expected_text = "response envelope to contain result (success)"
        else:
            expected_text = f"response error.code == {expected}"
        self._fail(
            assertion=assertion,
            expected_text=expected_text,
            actual_text=f"resolved STATUS was {self._value_to_text(actual_status)}",
            actual=actual_status,
        )
        return False

    def _evaluate_exists(self, assertion: Assert, values: list[Any]) -> bool:
        condition = assertion.expected_value
        if not isinstance(condition, str):
            self._fail(
                assertion=assertion,
                expected_text='EXISTS expects a condition string like name == "run_sql"',
                actual_text=f"got {self._value_to_text(condition)}",
                actual=values,
            )

        try:
            left_query, operator, right_value = self._parse_condition(condition)
        except ValueError:
            self._fail(
                assertion=assertion,
                expected_text="EXISTS condition must be: <field> <op> <value>",
                actual_text=f"got {condition}",
                actual=values,
            )
        for entry in values:
            candidates = self._extract_relative_values(entry, left_query)
            for candidate in candidates:
                if self._evaluate_scalar_predicate(
                    predicate=operator,
                    actual=candidate,
                    expected=right_value,
                    actual_exists=True,
                ):
                    return True

        self._fail(
            assertion=assertion,
            expected_text=f"{condition} found in {assertion.query} array",
            actual_text=f"no matching element found in {self._value_to_text(values)}",
            actual=values,
        )
        return False

    def _evaluate_count(self, assertion: Assert, values: list[Any]) -> bool:
        condition = assertion.expected_value
        if not isinstance(condition, str):
            self._fail(
                assertion=assertion,
                expected_text="COUNT expects a condition string like >= 1 or == 5",
                actual_text=f"got {self._value_to_text(condition)}",
                actual=len(values),
            )

        match = re.match(r"^\s*(==|!=|>=|<=|>|<)\s*(-?\d+)\s*$", condition)
        if match is None:
            self._fail(
                assertion=assertion,
                expected_text="COUNT condition must be: <op> <integer>",
                actual_text=f"got {condition}",
                actual=len(values),
            )

        operator = match.group(1)
        expected_count = int(match.group(2))
        actual_count = len(values)
        passed = self._evaluate_numeric_predicate(operator, actual_count, expected_count)
        if passed:
            return True

        self._fail(
            assertion=assertion,
            expected_text=f"count({assertion.query}) {operator} {expected_count}",
            actual_text=f"count was {actual_count}",
            actual=actual_count,
        )
        return False

    def _resolve_query(self, query: str, response: dict[str, Any]) -> list[Any]:
        if query == "jsonrpc":
            return [response["jsonrpc"]] if "jsonrpc" in response else []
        if query == "id":
            return [response["id"]] if "id" in response else []
        if query == "isError":
            result = response.get("result")
            if isinstance(result, dict) and "isError" in result:
                return [result["isError"]]
            return []
        if query == "protocolVersion":
            result = response.get("result")
            if isinstance(result, dict) and "protocolVersion" in result:
                return [result["protocolVersion"]]
            return []
        if query == "serverInfo.name":
            result = response.get("result")
            if not isinstance(result, dict):
                return []
            server_info = result.get("serverInfo")
            if isinstance(server_info, dict) and "name" in server_info:
                return [server_info["name"]]
            return []

        if (
            query.startswith("result.")
            or query == "result"
            or query.startswith("error.")
            or query == "error"
        ):
            return self._extract_jsonpath_values(query, response)

        result_root = response.get("result")
        if isinstance(result_root, dict):
            values = self._extract_jsonpath_values(query, result_root)
            if values:
                return values
            fallback = self._extract_dotted_values(result_root, query)
            if fallback:
                return fallback

        values = self._extract_jsonpath_values(query, response)
        if values:
            return values

        return self._extract_dotted_values(response, query)

    def _extract_jsonpath_values(self, query: str, target: Any) -> list[Any]:
        try:
            return [match.value for match in parse_jsonpath(query).find(target)]
        except Exception:
            return []

    def _extract_dotted_values(self, target: Any, query: str) -> list[Any]:
        if "[" in query or "]" in query or "?" in query:
            return []
        if not query:
            return []

        current: list[Any] = [target]
        for part in query.split("."):
            next_values: list[Any] = []
            for value in current:
                if isinstance(value, dict):
                    if part in value:
                        next_values.append(value[part])
                    continue
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and part in item:
                            next_values.append(item[part])
            if not next_values:
                return []
            current = next_values
        return current

    def _extract_relative_values(self, target: Any, query: str) -> list[Any]:
        values = self._extract_jsonpath_values(query, target)
        if values:
            return values
        return self._extract_dotted_values(target, query)

    def _evaluate_scalar_predicate(
        self,
        predicate: str,
        actual: Any,
        expected: Any,
        actual_exists: bool,
    ) -> bool:
        if predicate == "==":
            return self._equals(actual=actual, expected=expected, actual_exists=actual_exists)
        if predicate == "!=":
            return not self._equals(actual=actual, expected=expected, actual_exists=actual_exists)
        if predicate in {">", ">=", "<", "<="}:
            return self._evaluate_numeric_predicate(predicate, actual, expected)
        if predicate == "CONTAINS":
            return isinstance(actual, str) and isinstance(expected, str) and expected in actual
        if predicate == "MATCHES":
            return (
                isinstance(actual, str)
                and isinstance(expected, str)
                and re.search(expected, actual) is not None
            )
        return False

    def _equals(self, actual: Any, expected: Any, actual_exists: bool) -> bool:
        if isinstance(expected, TemplateString):
            return isinstance(actual, str) and actual == repr(expected)

        if isinstance(expected, FuzzyType):
            return self._match_fuzzy(expected, actual, actual_exists)

        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                return False
            return self._is_subset(expected, actual)

        if isinstance(expected, list):
            if not isinstance(actual, list):
                return False
            if len(expected) != len(actual):
                return False
            return all(
                self._equals(actual=a, expected=e, actual_exists=True)
                for e, a in zip(expected, actual)
            )

        return actual == expected

    def _is_subset(self, expected: dict[str, Any], actual: dict[str, Any]) -> bool:
        for key, expected_value in expected.items():
            if key not in actual:
                if isinstance(expected_value, FuzzyType) and expected_value.optional:
                    continue
                return False
            if not self._equals(actual=actual[key], expected=expected_value, actual_exists=True):
                return False
        return True

    def _match_fuzzy(self, fuzzy: FuzzyType, actual: Any, actual_exists: bool) -> bool:
        if not actual_exists:
            return fuzzy.optional
        if fuzzy.type_name == "string":
            return isinstance(actual, str)
        if fuzzy.type_name == "number":
            return isinstance(actual, int | float) and not isinstance(actual, bool)
        if fuzzy.type_name == "boolean":
            return isinstance(actual, bool)
        if fuzzy.type_name == "array":
            return isinstance(actual, list)
        if fuzzy.type_name == "object":
            return isinstance(actual, dict)
        return False

    def _evaluate_numeric_predicate(self, predicate: str, actual: Any, expected: Any) -> bool:
        left = self._to_number(actual)
        right = self._to_number(expected)
        if left is None or right is None:
            return False
        if predicate == ">":
            return left > right
        if predicate == ">=":
            return left >= right
        if predicate == "<":
            return left < right
        if predicate == "<=":
            return left <= right
        if predicate == "==":
            return left == right
        if predicate == "!=":
            return left != right
        return False

    def _parse_condition(self, condition: str) -> tuple[str, str, Any]:
        for operator in ("==", "!=", ">=", "<=", ">", "<"):
            marker = f" {operator} "
            if marker in condition:
                left, right = condition.split(marker, 1)
                return left.strip(), operator, self._coerce_literal(right.strip())

        raise ValueError(f"Invalid EXISTS condition: {condition}")

    def _coerce_literal(self, value: str) -> Any:
        if value == "true":
            return True
        if value == "false":
            return False
        if value in {"null", "none"}:
            return None
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            return value[1:-1]
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value

    def _coerce_actual(self, values: list[Any]) -> Any:
        if not values:
            return None
        if len(values) == 1:
            return values[0]
        return values

    def _extract_error_code(self, response: dict[str, Any]) -> int | None:
        error = response.get("error")
        if not isinstance(error, dict):
            return None
        code = error.get("code")
        return self._to_int(code)

    def _to_int(self, value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None

    def _to_number(self, value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    def _value_to_text(self, value: Any) -> str:
        if isinstance(value, TemplateString):
            return repr(value)
        if isinstance(value, str):
            return value
        return repr(value)

    def _fail(
        self,
        assertion: Assert,
        expected_text: str,
        actual_text: str,
        actual: Any,
    ) -> NoReturn:
        message = (
            f"ASSERT {assertion.query} {assertion.predicate} "
            f"{self._value_to_text(assertion.expected_value)}: FAILED\n"
            f"  Expected: {expected_text}\n"
            f"  Actual: {actual_text}"
        )
        raise AssertionError(
            message=message,
            query=assertion.query,
            expected=assertion.expected_value,
            actual=actual,
        )
