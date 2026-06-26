"""Parse-time exceptions for MCP-Hurl."""


class McphParseError(Exception):
    """Raised when parsing a .mcph file fails."""

    def __init__(
        self,
        message: str,
        line_number: int | None = None,
        source_line: str | None = None,
    ) -> None:
        self.line_number = line_number
        self.source_line = source_line
        parts = []
        if line_number is not None:
            parts.append(f"Error at line {line_number}: {message}")
        else:
            parts.append(f"Error: {message}")
        if source_line is not None:
            parts.append(f"  {source_line.strip()}")
            parts.append("  ^---")
        super().__init__("\n".join(parts))
