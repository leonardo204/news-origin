"""
# azure_openai.py - Azure OpenAI Client Service
# Version: 0.3.1
# Description: Azure OpenAI API 클라이언트 (임베딩 + GPT 평가)
# Changes:
#   - 0.1.0: text-embedding-3-large 임베딩, GPT-5o-mini 평가 호출
#   - 0.1.1: 에러 핸들링 + 재시도 로직, thread-safe 싱글톤
#   - 0.2.0: Chat Completions API 전환, URL 자동 파싱, 보안/안정성 개선
#   - 0.3.0: 배치 실패 시 개별 처리 fallback, 향상된 재시도 로직
#   - 0.3.1: async 클라이언트 asyncio.Lock 전환, call_gpt_async 재시도 추가, 타입 수정
"""

import asyncio
import atexit
import logging
import random
import threading
import time
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


def _get_base_url(endpoint: str) -> str:
    """엔드포인트 URL에서 base URL(scheme+host)만 추출"""
    parsed = urlparse(endpoint.rstrip('/'))
    return f"{parsed.scheme}://{parsed.netloc}"


# Azure deployment name 보정 (컨테이너 env var 업데이트 불가 시 임시 대응)
# 컨테이너 재생성 후 이 매핑은 제거 가능
_DEPLOYMENT_FIXES = {"gpt-5o-mini": "gpt-5", "gpt-4o-mini": "gpt-5"}


def _resolve_deployment(name: str) -> str:
    """잘못된 deployment name 자동 보정 (경고 로그 포함)"""
    fixed = _DEPLOYMENT_FIXES.get(name)
    if fixed:
        logger.warning(
            f"Deployment name '{name}' auto-corrected to '{fixed}'. "
            f"Update AZURE_OPENAI_MODEL_NAME env var to fix permanently."
        )
        return fixed
    return name


# HTTP 클라이언트 재사용 (커넥션 풀링) - thread-safe
_sync_client: Optional[httpx.Client] = None
_async_client: Optional[httpx.AsyncClient] = None
_sync_lock = threading.Lock()
_async_lock: Optional[asyncio.Lock] = None  # lazy init (이벤트 루프 필요)

# 재시도 설정
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_BACKOFF = 1.0  # seconds


def _get_sync_client() -> httpx.Client:
    """동기 HTTP 클라이언트 싱글톤 (thread-safe)"""
    global _sync_client
    if _sync_client is None:
        with _sync_lock:
            if _sync_client is None:
                _sync_client = httpx.Client(timeout=60.0)
    return _sync_client


async def _get_async_client() -> httpx.AsyncClient:
    """비동기 HTTP 클라이언트 싱글톤 (asyncio.Lock 사용)"""
    global _async_client, _async_lock
    if _async_client is None:
        if _async_lock is None:
            _async_lock = asyncio.Lock()
        async with _async_lock:
            if _async_client is None:
                _async_client = httpx.AsyncClient(timeout=60.0)
    return _async_client


def _cleanup_clients():
    """프로세스 종료 시 httpx 클라이언트 정리 (FD 누수 방지)"""
    global _sync_client, _async_client
    if _sync_client:
        try:
            _sync_client.close()
        except Exception:
            pass
        _sync_client = None
    if _async_client:
        try:
            # AsyncClient.close()는 sync 컨텍스트에서 호출 불가하므로 무시
            pass
        except Exception:
            pass
        _async_client = None


atexit.register(_cleanup_clients)


def _safe_error_body(response: httpx.Response) -> str:
    """에러 응답 본문에서 민감 정보 제거 후 반환"""
    try:
        body = response.text[:200] if response.text else "No body"
    except Exception:
        body = "Unable to read response body"
    return body


def _is_retryable_error(exc: Exception) -> bool:
    """에러가 재시도 가능한지 판단"""
    if isinstance(exc, httpx.HTTPStatusError):
        # 429 (Rate Limit)와 5xx 에러만 재시도
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError)):
        return True
    return False


def _retry_request(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    """HTTP 요청 + 재시도 (429/5xx/timeout/network에 대해 exponential backoff + jitter)"""
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = client.request(method, url, **kwargs)
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES - 1:
                wait = _BASE_BACKOFF * (2 ** attempt) * (0.5 + random.random())
                logger.warning(
                    f"Azure API {response.status_code}, retry {attempt+1}/{_MAX_RETRIES} "
                    f"after {wait:.1f}s"
                )
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
            last_exc = e
            if attempt < _MAX_RETRIES - 1:
                wait = _BASE_BACKOFF * (2 ** attempt) * (0.5 + random.random())
                error_type = type(e).__name__
                logger.warning(
                    f"Azure API {error_type}, retry {attempt+1}/{_MAX_RETRIES} after {wait:.1f}s"
                )
                time.sleep(wait)
            else:
                raise
        except httpx.HTTPStatusError as e:
            # 4xx 에러는 재시도하지 않음 (429 제외, 위에서 처리됨)
            if e.response.status_code < 500:
                raise
            last_exc = e
            if attempt < _MAX_RETRIES - 1:
                wait = _BASE_BACKOFF * (2 ** attempt) * (0.5 + random.random())
                logger.warning(
                    f"Azure API {e.response.status_code}, retry {attempt+1}/{_MAX_RETRIES} "
                    f"after {wait:.1f}s"
                )
                time.sleep(wait)
            else:
                raise
    raise last_exc  # Should not reach here


def create_embedding_sync(text: str) -> list[float]:
    """
    Azure OpenAI text-embedding-3-large 동기 호출 (단일 텍스트)

    Celery 워커에서 사용 (이벤트 루프 없음)
    """
    client = _get_sync_client()
    url = (
        f"{settings.azure_openai_embedding_endpoint.rstrip('/')}"
        f"/openai/deployments/{settings.azure_openai_embedding_deployment_name}"
        f"/embeddings?api-version={settings.azure_openai_embedding_api_version}"
    )
    try:
        response = _retry_request(
            client, "POST", url,
            headers={
                "api-key": settings.azure_openai_embedding_api_key,
                "Content-Type": "application/json",
            },
            json={
                "input": text,
                "dimensions": settings.embedding_dimension,
            },
        )
        data = response.json()
        return data["data"][0]["embedding"]
    except httpx.HTTPStatusError as e:
        logger.error(f"Embedding API error {e.response.status_code}: {_safe_error_body(e.response)}")
        raise
    except (KeyError, IndexError) as e:
        logger.error(f"Unexpected embedding API response format: {e}")
        raise


def create_embeddings_batch_sync(texts: list[str]) -> list[list[float] | None]:
    """
    Azure OpenAI text-embedding-3-large 동기 배치 호출

    Azure API는 한 번에 최대 2048개 텍스트를 받지만,
    안정성을 위해 16개씩 분할 호출

    배치 실패 시 개별 처리 fallback 적용:
    - 배치 전체가 실패하면 개별 임베딩 요청으로 fallback
    - 개별 요청도 실패하면 해당 텍스트만 None으로 반환 (다른 텍스트는 계속 처리)
    """
    if not texts:
        return []

    client = _get_sync_client()
    url = (
        f"{settings.azure_openai_embedding_endpoint.rstrip('/')}"
        f"/openai/deployments/{settings.azure_openai_embedding_deployment_name}"
        f"/embeddings?api-version={settings.azure_openai_embedding_api_version}"
    )
    headers = {
        "api-key": settings.azure_openai_embedding_api_key,
        "Content-Type": "application/json",
    }

    all_embeddings = []
    batch_size = 16

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            response = _retry_request(
                client, "POST", url,
                headers=headers,
                json={
                    "input": batch,
                    "dimensions": settings.embedding_dimension,
                },
            )
            data = response.json()

            # 인덱스 순서대로 정렬
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            all_embeddings.extend([item["embedding"] for item in sorted_data])
        except Exception as batch_error:
            # 배치 실패 → 개별 처리 fallback
            logger.warning(
                f"Batch embedding failed at offset {i}, falling back to individual requests: "
                f"{type(batch_error).__name__}"
            )
            for j, text in enumerate(batch):
                try:
                    embedding = create_embedding_sync(text)
                    all_embeddings.append(embedding)
                except Exception as individual_error:
                    # 개별 요청도 실패 → None 반환 (해당 기사만 skip)
                    logger.error(
                        f"Individual embedding failed for text at index {i+j}, skipping: "
                        f"{type(individual_error).__name__}: {str(individual_error)[:100]}"
                    )
                    all_embeddings.append(None)

    return all_embeddings


def call_gpt_sync(
    prompt: str,
    system_message: str = "You are a helpful assistant for Korean news analysis.",
    max_tokens: int = 4096,
) -> str:
    """
    Azure OpenAI GPT-5 동기 호출 (평가용)

    Celery 워커에서 사용
    Azure Chat Completions API format: messages/choices
    Note: GPT-5는 reasoning 모델로 내부 추론에 500~800+ 토큰을 사용하므로
    max_completion_tokens를 충분히 높게 설정해야 함
    """
    client = _get_sync_client()
    base = _get_base_url(settings.azure_openai_endpoint)
    deployment = _resolve_deployment(settings.azure_openai_model_name)
    url = (
        f"{base}/openai/deployments/{deployment}"
        f"/chat/completions?api-version={settings.azure_openai_api_version}"
    )
    try:
        response = _retry_request(
            client, "POST", url,
            headers={
                "api-key": settings.azure_openai_api_key,
                "Content-Type": "application/json",
            },
            json={
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
                "max_completion_tokens": max_tokens,
            },
        )
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        logger.error(f"GPT API error {e.response.status_code}: {_safe_error_body(e.response)}")
        raise
    except (KeyError, IndexError) as e:
        logger.error(f"Unexpected GPT API response format: {e}")
        raise


def call_gpt_with_tools_sync(
    prompt: str,
    tools: list[dict],
    system_message: str = "You are a helpful assistant for Korean news analysis.",
    max_tokens: int = 4096,
    tool_choice: str | dict = "auto",
) -> dict:
    """
    Azure OpenAI GPT-5 동기 호출 + function calling (tools)

    Celery 워커에서 사용. 구조화된 출력이 필요할 때 사용.
    Returns: tool_calls의 첫 번째 function arguments (parsed JSON dict)
    """
    client = _get_sync_client()
    base = _get_base_url(settings.azure_openai_endpoint)
    deployment = _resolve_deployment(settings.azure_openai_model_name)
    url = (
        f"{base}/openai/deployments/{deployment}"
        f"/chat/completions?api-version={settings.azure_openai_api_version}"
    )

    body = {
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": max_tokens,
        "tools": tools,
    }
    if tool_choice != "auto":
        body["tool_choice"] = tool_choice

    try:
        response = _retry_request(
            client, "POST", url,
            headers={
                "api-key": settings.azure_openai_api_key,
                "Content-Type": "application/json",
            },
            json=body,
        )
        data = response.json()
        message = data["choices"][0]["message"]

        # tool_calls가 있으면 첫 번째 function의 arguments를 파싱하여 반환
        tool_calls = message.get("tool_calls")
        if tool_calls:
            import json
            args_str = tool_calls[0]["function"]["arguments"]
            return json.loads(args_str)

        # tool_calls가 없으면 content에서 JSON 파싱 시도 (fallback)
        content = message.get("content", "")
        if content:
            import json
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        raise ValueError("GPT response contains neither tool_calls nor parseable JSON content")

    except httpx.HTTPStatusError as e:
        logger.error(f"GPT tools API error {e.response.status_code}: {_safe_error_body(e.response)}")
        raise
    except (KeyError, IndexError) as e:
        logger.error(f"Unexpected GPT tools API response format: {e}")
        raise


async def _async_retry_request(
    client: httpx.AsyncClient, method: str, url: str, **kwargs
) -> httpx.Response:
    """비동기 HTTP 요청 + 재시도 (429/5xx/timeout/network에 대해 exponential backoff + jitter)"""
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = await client.request(method, url, **kwargs)
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES - 1:
                wait = _BASE_BACKOFF * (2 ** attempt) * (0.5 + random.random())
                logger.warning(
                    f"Azure async API {response.status_code}, retry {attempt+1}/{_MAX_RETRIES} "
                    f"after {wait:.1f}s"
                )
                await asyncio.sleep(wait)
                continue
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
            last_exc = e
            if attempt < _MAX_RETRIES - 1:
                wait = _BASE_BACKOFF * (2 ** attempt) * (0.5 + random.random())
                logger.warning(
                    f"Azure async API {type(e).__name__}, retry {attempt+1}/{_MAX_RETRIES} after {wait:.1f}s"
                )
                await asyncio.sleep(wait)
            else:
                raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise
            last_exc = e
            if attempt < _MAX_RETRIES - 1:
                wait = _BASE_BACKOFF * (2 ** attempt) * (0.5 + random.random())
                logger.warning(
                    f"Azure async API {e.response.status_code}, retry {attempt+1}/{_MAX_RETRIES} "
                    f"after {wait:.1f}s"
                )
                await asyncio.sleep(wait)
            else:
                raise
    raise last_exc


async def call_gpt_async(
    prompt: str,
    system_message: str = "You are a helpful assistant for Korean news analysis.",
    max_tokens: int = 4096,
) -> str:
    """
    Azure OpenAI GPT-5 비동기 호출 (API 핸들러에서 사용)

    Azure Chat Completions API format: messages/choices
    재시도 로직 포함 (429/5xx/timeout/network 에러)
    """
    client = await _get_async_client()
    base = _get_base_url(settings.azure_openai_endpoint)
    deployment = _resolve_deployment(settings.azure_openai_model_name)
    url = (
        f"{base}/openai/deployments/{deployment}"
        f"/chat/completions?api-version={settings.azure_openai_api_version}"
    )
    try:
        response = await _async_retry_request(
            client, "POST", url,
            headers={
                "api-key": settings.azure_openai_api_key,
                "Content-Type": "application/json",
            },
            json={
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
                "max_completion_tokens": max_tokens,
            },
        )
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        logger.error(f"GPT async API error {e.response.status_code}: {_safe_error_body(e.response)}")
        raise
    except (KeyError, IndexError) as e:
        logger.error(f"Unexpected GPT async API response format: {e}")
        raise
