"""Local stdio MCP server with a fixed teaching identity and read-only tools."""
from datetime import date
import json

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from practice.enterprise_ai.policy_agent import lookup_limit
from practice.enterprise_ai.retrieval_baseline import DATA, eligible_sources


server = FastMCP("policy-course")
TENANT = "tenant-a"  # Trusted local fixture; remote use requires authenticated context.


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of: date


class SourceRequest(PolicyRequest):
    source_id: str = Field(min_length=1, max_length=120)


class PolicyResult(BaseModel):
    limit_percent: int
    source_id: str


class SourceResult(BaseModel):
    source_id: str
    section: str
    text: str


def policies():
    return json.loads((DATA / "policies.json").read_text(encoding="utf-8"))


@server.tool()
def get_prepayment_limit(request: PolicyRequest) -> PolicyResult:
    """Read the fixed teaching tenant's policy for an explicit business date."""
    return PolicyResult(**lookup_limit(policies(), TENANT, request.as_of.isoformat()))


@server.tool()
def get_policy_source(request: SourceRequest) -> SourceResult:
    """Read an authorized source; unavailable and other-tenant sources are hidden."""
    rows = eligible_sources(policies(), TENANT, request.as_of.isoformat())
    for row in rows:
        if row["source_id"] == request.source_id:
            return SourceResult(**{key: row[key] for key in ("source_id", "section", "text")})
    raise ValueError("Source unavailable")


if __name__ == "__main__":
    server.run(transport="stdio")
