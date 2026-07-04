import re
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Any, Protocol

from .config import get_settings
from .embedding import embeddings

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:  # pragma: no cover - exercised only in incomplete envs
    psycopg2 = None
    sql = None

try:
    from FlagEmbedding import FlagReranker
except ImportError:  # pragma: no cover - exercised only in incomplete envs
    FlagReranker = None

try:
    from langchain_community.vectorstores import FAISS
except ImportError:  # pragma: no cover - exercised only in incomplete envs
    FAISS = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - exercised only in incomplete envs
    ChatOpenAI = None


class RerankerProtocol(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]:
        ...


class NoReranker:
    def score(self, query: str, passages: list[str]) -> list[float]:
        return [0.0 for _ in passages]


class BGEReranker:
    """Adapter for BAAI bge-reranker models using FlagEmbedding FlagReranker."""

    def __init__(
        self,
        model_name: str,
        *,
        use_fp16: bool = True,
        model_factory: Callable[..., Any] | None = None,
    ) -> None:
        factory = model_factory or FlagReranker
        if factory is None:
            raise RuntimeError(
                "FlagEmbedding is required for reranking. Install project dependencies "
                "or pass a custom RerankerProtocol implementation."
            )
        self._model = factory(model_name, use_fp16=use_fp16)

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []

        pairs = [[query, passage] for passage in passages]
        raw_scores = self._model.compute_score(pairs)
        if isinstance(raw_scores, (int, float)):
            return [float(raw_scores)]
        return [float(score) for score in raw_scores]


@lru_cache
def get_reranker() -> RerankerProtocol:
    settings = get_settings()
    return BGEReranker(settings.reranker_model, use_fp16=True)


@lru_cache
def get_llm() -> Any:
    settings = get_settings()
    if ChatOpenAI is None:
        raise RuntimeError("langchain-openai is required for LLM analysis.")
    if not settings.deepseek_api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not configured. Create a .env file from .env.example "
            "or set the environment variable before calling LLM functions."
        )
    llm_kwargs = {
        "model": settings.llm_model,
        "openai_api_key": settings.deepseek_api_key,
        "openai_api_base": settings.llm_api_base,
        "max_tokens": settings.llm_max_tokens,
    }
    return ChatOpenAI(**llm_kwargs)


def convert_str_to_list(input_str: str) -> list[str]:
    input_str = input_str.strip("[]")
    result_list = input_str.split(",")
    return [item.strip() for item in result_list if item.strip()]


def analyze_query(query: dict[str, Any]) -> list[str]:
    prompt = f'''你是一个擅长分析近义词的汉语学家。
    你需要分析<{query['activity_name']}>相关的近义词有哪些,返回前3个最接近的近义词.
    注意:你需要保证输出格式如下,多个词之间用逗号','分开：
    [在这里输入你认为的近义词1,在这里输入你认为的近义词2,在这里输入你认为的近义词3]'''
    result = get_llm().invoke(prompt).content
    return convert_str_to_list(result)


def get_knowledge_based_answer(
    vector_db_path: str,
    queries: list[str],
    top_k_embedding_docs: int,
    top_k_rerank_docs: int,
    reranker: RerankerProtocol | None = None,
) -> str:
    if FAISS is None:
        raise RuntimeError("langchain-community is required for FAISS vector search.")

    top_rerank_knowledge_content: list[str] = []
    vector_db = FAISS.load_local(
        folder_path=vector_db_path,
        embeddings=embeddings,
        allow_dangerous_deserialization=True,
    )
    active_reranker = reranker or get_reranker()

    for query in queries:
        start_time = time.time()
        result = vector_db.similarity_search_with_score(
            query=query,
            k=top_k_embedding_docs,
        )
        end_time = time.time()
        _ = end_time - start_time

        docs = [doc for doc, _ in result]
        passages = [doc.page_content for doc in docs]

        start_time = time.time()
        scores = active_reranker.score(query, passages)
        end_time = time.time()
        _ = end_time - start_time

        if len(scores) != len(docs):
            raise RuntimeError(
                f"Reranker returned {len(scores)} scores for {len(docs)} passages."
            )

        sorted_rerank_scores = sorted(
            zip(docs, scores, strict=True),
            key=lambda item: item[1],
            reverse=True,
        )
        for doc, _score in sorted_rerank_scores[:top_k_rerank_docs]:
            page_content = doc.page_content.replace("\r\n", "\n").replace("\r", "\n")
            top_rerank_knowledge_content.append(page_content)

    joined_content = "\n\n".join(top_rerank_knowledge_content)
    print(
        f"type(top_rerank_knowledge_content): {type(joined_content)},\n "
        f"top_rerank_knowledge_content:\n {joined_content}"
    )
    return joined_content


def _connect_postgres() -> Any:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 or psycopg2-binary is required for PostgreSQL access.")

    settings = get_settings()
    if settings.database_url:
        return psycopg2.connect(settings.database_url)

    conn_params = {
        "dbname": settings.postgres_db,
        "user": settings.postgres_user,
        "password": settings.postgres_password,
        "host": settings.postgres_host,
        "port": str(settings.postgres_port),
    }
    return psycopg2.connect(**conn_params)


def query_uuid(uuid_str: str, table_name: str) -> list[dict[str, Any]] | None:
    uuids = re.findall(r"activity_uuid_product_uuid: ([a-f0-9\-]+_[a-f0-9\-]+)", uuid_str)
    uuids = list(set(uuids))
    print(type(uuids), len(uuids), uuids)

    if not uuids:
        return None

    start_time = time.time()
    conn = _connect_postgres()
    cursor = conn.cursor()

    if sql is None:
        raise RuntimeError("psycopg2.sql is required for safe table name handling.")
    db_query = sql.SQL(
        "SELECT activity_name, geography, reference_product_unit "
        "FROM {} WHERE activity_uuid_product_uuid IN %s"
    ).format(sql.Identifier(table_name))

    cursor.execute(db_query, (tuple(uuids),))
    results = cursor.fetchall()

    cursor.close()
    conn.close()

    end_time = time.time()
    _ = end_time - start_time

    keys = ["activity_name", "geography", "reference_product_unit"]
    return [dict(zip(keys, row, strict=True)) for row in results]


def analyze_sql_results1(query: str, sql_results: list[Any]) -> str:
    start_time = time.time()
    prompt = f'''你是一个分析师，你需要将【已知】中的多条数据按照和【目标】的相关性进行分析，最后对【已知】的内容进行排序。

    排序需要参考三方面因素：活动名(activity_name),单位(reference_product_unit),地理(geography):
    具体的步骤如下：
    1.首先，将与目标活动名(activity_name)最相关的选项排在最前面。
    2.然后，在活动名相同的情况下，考虑单位(reference_product_unit)相关性。
    3.最后，在活动名和单位相同的情况下，考虑地理(geography)相关性。

    【目标】
    {query}

    【已知】
    {sql_results}

    注意，你需要保证返回的格式如下，格式的要求在xml标签<format>里面。
    <format>
    1.<在这里输入你认为第1适合的答案>;
    2.<在这里输入你认为第2适合的答案>;
    ……
    n.<在这里输入你认为第n适合的答案>;
    </format>
    '''
    print(f"提示词:{prompt}")
    result = get_llm().invoke(prompt)
    end_time = time.time()
    _ = end_time - start_time
    return result.content


def analyze_sql_results2(query: str, sql_results: list[Any]) -> str:
    start_time = time.time()
    prompt = f'''你是一个分析师，你需要将【已知】中的多条数据按照和【目标】的相关性进行分析，然后过滤掉不符合要求的内容，最后对【已知】的内容进行排序。
    过滤需要考虑两方面因素：活动名(activity_name),单位(reference_product_unit):
    具体的步骤如下：
    1.首先，考虑与目标活动名(activity_name)的相关性。如果是【已知】中的活动名和【目标】的活动名不相关，就直接舍弃。
    2.然后，在活动名符合要求的情况下，考虑单位(reference_product_unit)相关性。如果是【已知】中的单位和【目标】的单位不是同一个量纲，就直接舍弃。

    排序需要参考三方面因素：活动名(activity_name),单位(reference_product_unit),地理(geography):
    具体的步骤如下：
    1.首先，将与目标活动名(activity_name)最相关的选项排在最前面。
    2.然后，在活动名相同的情况下，考虑单位(reference_product_unit)相关性。
    3.最后，在活动名和单位相同的情况下，考虑地理(geography)相关性。

    【目标】
    {query}

    【已知】
    {sql_results}

    注意，你需要保证返回的格式如下，格式的要求在xml标签<format>里面。
    <format>
    1.<在这里输入你认为第1适合的答案>;
    2.<在这里输入你认为第2适合的答案>;
    ……
    n.<在这里输入你认为第n适合的答案>;
    </format>
    '''
    print(f"提示词:{prompt}")
    result = get_llm().invoke(prompt)
    end_time = time.time()
    _ = end_time - start_time
    return result.content


def extract_format_content(xml_str: str) -> str:
    match = re.search(r"<format>(.*?)</format>", xml_str, re.DOTALL)
    if not match or not match.group(1).strip():
        return "没有找到 <format> 和 </format> 之间的内容"
    return match.group(1).strip()
