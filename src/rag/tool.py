"""RAG Tool for LongDelta-AI Agent.

This module provides a tool for the agent to retrieve relevant
policy context from the knowledge base.
"""
from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.rag.knowledge_base import (
    KnowledgeBase,
    initialize_knowledge_base,
)


class PolicyContext(BaseModel):
    """Policy context returned by the RAG tool."""
    relevant_policies: list[str] = Field(default_factory=list, description="Relevant policy titles")
    context_text: str = Field(..., description="Concatenated relevant context")
    sources: list[str] = Field(default_factory=list, description="Source URLs")


class RagToolOutput(BaseModel):
    """RAG tool output model."""
    query: str = Field(..., description="Original query")
    result_count: int = Field(..., description="Number of results found")
    policy_context: PolicyContext = Field(..., description="Retrieved context")


# Global knowledge base instance
_kb: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    """Get or initialize the knowledge base."""
    global _kb
    if _kb is None:
        _kb = initialize_knowledge_base()
    return _kb


@tool
def search_policy_context(
    query: str,
    max_chars: int = 2000,
    filter_region: str | None = None,
    filter_category: str | None = None
) -> dict[str, Any]:
    """
    Search for relevant policy context to enhance economic analysis.

    This tool retrieves relevant policy documents from the knowledge base
    to provide context for the economic analysis agent.

    Args:
        query: The search query (e.g., "安徽新能源汽车产业政策")
        max_chars: Maximum character length of returned context
        filter_region: Filter results by region (e.g., "安徽", "江苏")
        filter_category: Filter by policy category (e.g., "产业政策", "营商环境")

    Returns:
        Dict containing:
        - query: Original query
        - result_count: Number of results
        - policy_context: Relevant policy titles, context text, and sources
    """
    try:
        kb = get_knowledge_base()

        # Search for relevant documents
        results = kb.search(
            query=query,
            k=5,
            filter_region=filter_region,
            filter_category=filter_category
        )

        # Build context
        relevant_policies = []
        sources = []
        context_parts = []

        for result in results:
            doc = result.document
            relevant_policies.append(doc.title)
            sources.append(doc.source)

            # Truncate if needed
            content = doc.content
            if len(content) > 500:
                content = content[:500] + "..."

            context_parts.append(f"【{doc.title}】({doc.source}): {content}")

        context_text = "\n\n".join(context_parts)

        # Truncate to max_chars
        if len(context_text) > max_chars:
            context_text = context_text[:max_chars] + "..."

        output = RagToolOutput(
            query=query,
            result_count=len(results),
            policy_context=PolicyContext(
                relevant_policies=relevant_policies,
                context_text=context_text,
                sources=sources
            )
        )

        return output.model_dump()

    except Exception as e:
        return {
            "query": query,
            "result_count": 0,
            "policy_context": PolicyContext(
                relevant_policies=[],
                context_text=f"Error searching knowledge base: {str(e)}",
                sources=[]
            ).model_dump()
        }


@tool
def get_regional_policy(region: str) -> dict[str, Any]:
    """
    Get all policies related to a specific region.

    Args:
        region: Region name (e.g., "安徽", "江苏", "上海", "浙江")

    Returns:
        All policies related to the region
    """
    try:
        kb = get_knowledge_base()
        results = kb.search(query=f"{region}政策", k=10, filter_region=region)

        policies = []
        for result in results:
            doc = result.document
            policies.append({
                "title": doc.title,
                "source": doc.source,
                "category": doc.category,
                "date": doc.date,
                "content_preview": doc.content[:200] + "...",
                "relevance_score": result.score
            })

        return {
            "region": region,
            "policy_count": len(policies),
            "policies": policies
        }

    except Exception as e:
        return {
            "region": region,
            "policy_count": 0,
            "policies": [],
            "error": str(e)
        }


def add_policy_to_knowledge_base(
    title: str,
    content: str,
    source: str,
    region: str | None = None,
    category: str | None = None,
    date: str | None = None
) -> dict[str, Any]:
    """
    Add a new policy document to the knowledge base.

    Args:
        title: Policy document title
        content: Full text content
        source: Source URL or reference
        region: Related region
        category: Policy category
        date: Publication date

    Returns:
        Result of the operation
    """
    from src.rag.knowledge_base import PolicyDocument

    kb = get_knowledge_base()

    doc = PolicyDocument(
        title=title,
        content=content,
        source=source,
        region=region,
        category=category,
        date=date
    )

    count = kb.add_documents([doc])

    return {
        "success": True,
        "title": title,
        "documents_added": count
    }
