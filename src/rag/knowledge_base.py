"""RAG Knowledge Base for LongDelta-AI.

This module provides RAG capabilities for policy document retrieval
to enhance economic analysis with relevant context.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore
from pydantic import BaseModel, Field

# Try to import optional dependencies
try:
    from langchain_community.vectorstores import Chroma
    from langchain_openai import OpenAIEmbeddings
    VECTORSTORE_AVAILABLE = True
except ImportError:
    VECTORSTORE_AVAILABLE = False


class PolicyDocument(BaseModel):
    """Policy document model."""
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content")
    source: str = Field(..., description="Source/URL")
    region: str | None = Field(default=None, description="Related region")
    category: str | None = Field(default=None, description="Policy category")
    date: str | None = Field(default=None, description="Publication date")


class KnowledgeBaseConfig(BaseModel):
    """Knowledge base configuration."""
    persist_directory: str = Field(default="./data/knowledge_base")
    collection_name: str = Field(default="policy_documents")
    embedding_model: str = Field(default="text-embedding-3-small")
    search_k: int = Field(default=5, description="Number of results to return")


class SearchResult(BaseModel):
    """Search result from knowledge base."""
    document: PolicyDocument
    score: float = Field(..., description="Similarity score")
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBase:
    """
    Knowledge Base for policy document retrieval.

    Supports:
    - Document ingestion from text/PDF files
    - Vector-based semantic search
    - Region-based filtering
    - Category-based filtering
    """

    def __init__(self, config: KnowledgeBaseConfig | None = None):
        """Initialize knowledge base."""
        if not VECTORSTORE_AVAILABLE:
            raise ImportError(
                "Vector store dependencies not installed. "
                "Install with: pip install langchain-community langchain-openai"
            )

        self.config = config or KnowledgeBaseConfig()
        self.config.persist_directory = str(Path(self.config.persist_directory))
        self._vectorstore: VectorStore | None = None
        self._retriever: BaseRetriever | None = None

    def _get_embeddings(self) -> Embeddings:
        """Get embedding model."""
        from src.utils.config import get_settings
        s = get_settings()

        return OpenAIEmbeddings(
            model=self.config.embedding_model,
            api_key=s.llm_api_key,
            base_url=s.llm_base_url
        )

    def _ensure_vectorstore(self):
        """Ensure vector store is initialized."""
        if self._vectorstore is None:
            embeddings = self._get_embeddings()

            # Create persist directory
            os.makedirs(self.config.persist_directory, exist_ok=True)

            # Try to load existing or create new
            if os.path.exists(os.path.join(self.config.persist_directory, "chroma.sqlite3")):
                self._vectorstore = Chroma(
                    persist_directory=self.config.persist_directory,
                    embedding_function=embeddings,
                    collection_name=self.config.collection_name
                )
            else:
                self._vectorstore = Chroma(
                    persist_directory=self.config.persist_directory,
                    embedding_function=embeddings,
                    collection_name=self.config.collection_name
                )

    def _ensure_retriever(self):
        """Ensure retriever is initialized."""
        self._ensure_vectorstore()
        if self._retriever is None:
            self._retriever = self._vectorstore.as_retriever(
                search_kwargs={"k": self.config.search_k}
            )

    def add_documents(
        self,
        documents: list[PolicyDocument],
        metadata: dict[str, Any] | None = None
    ) -> int:
        """
        Add documents to the knowledge base.

        Args:
            documents: List of policy documents
            metadata: Additional metadata to attach

        Returns:
            Number of documents added
        """
        self._ensure_vectorstore()

        docs = []
        for doc in documents:
            page_content = f"# {doc.title}\n\n{doc.content}"
            doc_metadata = {
                "source": doc.source,
                "region": doc.region,
                "category": doc.category,
                "date": doc.date,
                **(metadata or {})
            }
            docs.append(Document(page_content=page_content, metadata=doc_metadata))

        if docs:
            self._vectorstore.add_documents(docs)
            self._vectorstore.persist()

        return len(docs)

    def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None
    ) -> list[str]:
        """
        Add raw texts to the knowledge base.

        Args:
            texts: List of text strings
            metadatas: List of metadata dicts
            ids: List of document IDs

        Returns:
            List of document IDs
        """
        self._ensure_vectorstore()

        ids = self._vectorstore.add_texts(texts, metadatas=metadatas, ids=ids)
        self._vectorstore.persist()

        return ids

    def search(
        self,
        query: str,
        k: int | None = None,
        filter_region: str | None = None,
        filter_category: str | None = None
    ) -> list[SearchResult]:
        """
        Search for relevant documents.

        Args:
            query: Search query
            k: Number of results
            filter_region: Filter by region
            filter_category: Filter by category

        Returns:
            List of search results
        """
        self._ensure_retriever()

        # Build filter
        filter_dict = {}
        if filter_region:
            filter_dict["region"] = filter_region
        if filter_category:
            filter_dict["category"] = filter_category

        # Search
        search_kwargs = {"k": k or self.config.search_k}
        if filter_dict:
            search_kwargs["filter"] = filter_dict

        docs = self._vectorstore.similarity_search(query, **search_kwargs)

        # Calculate similarity scores
        results = []
        for doc in docs:
            # Get embedding similarity
            embedding = self._get_embeddings()
            query_embedding = embedding.embed_query(query)
            doc_embedding = embedding.embed_query(doc.page_content)

            import numpy as np
            similarity = np.dot(query_embedding, doc_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding)
            )

            # Extract document info from metadata
            title = doc.metadata.get("title", "Unknown")
            region = doc.metadata.get("region")
            category = doc.metadata.get("category")
            source = doc.metadata.get("source", "")
            date = doc.metadata.get("date")

            policy_doc = PolicyDocument(
                title=title,
                content=doc.page_content,
                source=source,
                region=region,
                category=category,
                date=date
            )

            results.append(SearchResult(
                document=policy_doc,
                score=float(similarity),
                metadata=doc.metadata
            ))

        return results

    def get_relevant_context(
        self,
        query: str,
        max_chars: int = 3000
    ) -> str:
        """
        Get relevant context for LLM prompt.

        Args:
            query: Search query
            max_chars: Maximum character length

        Returns:
            Concatenated context string
        """
        results = self.search(query, k=5)

        contexts = []
        for result in results:
            doc = result.document
            context = f"【来源: {doc.source}】\n{doc.content}"
            contexts.append(context)

            if sum(len(c) for c in contexts) > max_chars:
                break

        return "\n\n".join(contexts)

    def load_documents_from_directory(
        self,
        directory: str,
        file_pattern: str = "*.txt"
    ) -> int:
        """
        Load documents from a directory.

        Args:
            directory: Directory path
            file_pattern: File pattern to match

        Returns:
            Number of documents loaded
        """
        from langchain_community.document_loaders import DirectoryLoader, TextLoader

        loader = DirectoryLoader(
            directory,
            glob=file_pattern,
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"}
        )

        docs = loader.load()

        # Convert to PolicyDocuments and add
        policy_docs = []
        for doc in docs:
            filename = os.path.basename(doc.metadata.get("source", ""))
            policy_docs.append(PolicyDocument(
                title=filename,
                content=doc.page_content,
                source=doc.metadata.get("source", ""),
                region=None,
                category=None,
                date=None
            ))

        return self.add_documents(policy_docs)


# ==================== Sample Policy Data ====================

SAMPLE_POLICIES = [
    PolicyDocument(
        title="长三角一体化发展规划纲要",
        content="长三角地区一体化发展是国家战略，要求加强区域协调，推动高质量发展。重点任务包括：1) 加强基础设施互联互通；2) 推进产业协同发展；3) 共建绿色美丽长三角；4) 深化开放合作。",
        source="国务院文件",
        region="长三角",
        category="区域规划",
        date="2019"
    ),
    PolicyDocument(
        title="安徽省高质量发展政策",
        content="安徽省提出十大新兴产业发展计划，重点支持：新一代信息技术、新能源汽车、高端装备制造等。到2025年，战略性新兴产业产值占GDP比重达到40%以上。",
        source="安徽省政府",
        region="安徽",
        category="产业政策",
        date="2023"
    ),
    PolicyDocument(
        title="江苏省产业升级指导意见",
        content="江苏省推进传统产业数字化转型，重点发展智能制造、工业互联网。计划到2025年，数字经济核心产业增加值占GDP比重达到15%。",
        source="江苏省政府",
        region="江苏",
        category="产业政策",
        date="2023"
    ),
    PolicyDocument(
        title="上海市营商环境优化条例",
        content="上海市持续优化营商环境，推行一网通办、证照分离改革。重点降低企业制度性交易成本，打造国际一流营商环境高地。",
        source="上海市政府",
        region="上海",
        category="营商环境",
        date="2022"
    ),
    PolicyDocument(
        title="浙江省数字经济发展规划",
        content="浙江省建设数字经济强省，重点发展数字贸易、数字金融、智能物联。到2027年，数字经济总量达到12万亿元，核心产业增加值占GDP比重达到15%。",
        source="浙江省政府",
        region="浙江",
        category="数字经济",
        date="2024"
    ),
]


def initialize_knowledge_base() -> KnowledgeBase:
    """Initialize knowledge base with sample policies."""
    kb = KnowledgeBase()

    # Check if already populated
    kb._ensure_vectorstore()
    count = kb._vectorstore._collection.count()

    if count == 0:
        kb.add_documents(SAMPLE_POLICIES)

    return kb
