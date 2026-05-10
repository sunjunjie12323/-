import asyncio
import json
from typing import AsyncGenerator, Dict, List, Optional

import httpx
from loguru import logger

from app.config import settings


class LLMService:
    def __init__(self):
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.model_name = settings.LLM_MODEL_NAME
        self.default_temperature = settings.LLM_TEMPERATURE
        self.default_max_tokens = settings.LLM_MAX_TOKENS
        self._client: Optional[httpx.AsyncClient] = None
        self._max_retries = 5
        self._base_delay = 1.0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=30.0),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _retry_request(self, request_fn):
        delay = self._base_delay
        last_exception = None
        for attempt in range(self._max_retries):
            try:
                return await request_fn()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code == 429:
                    retry_after = exc.response.headers.get("retry-after")
                    if retry_after:
                        try:
                            wait_time = float(retry_after)
                        except ValueError:
                            wait_time = delay
                    else:
                        wait_time = delay
                    logger.warning(
                        f"Rate limited (429), retrying in {wait_time:.1f}s "
                        f"(attempt {attempt + 1}/{self._max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    delay = min(delay * 2, 60.0)
                    last_exception = exc
                elif status_code >= 500:
                    logger.warning(
                        f"Server error {status_code}, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self._max_retries})"
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 60.0)
                    last_exception = exc
                else:
                    logger.error(f"HTTP error {status_code}: {exc.response.text}")
                    raise
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                logger.warning(
                    f"Connection error: {exc}, retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{self._max_retries})"
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)
                last_exception = exc
            except Exception as exc:
                logger.error(f"Unexpected error during LLM request: {exc}")
                raise
        raise last_exception or RuntimeError("Max retries exceeded")

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async def _request():
            client = await self._get_client()
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        try:
            result = await self._retry_request(_request)
            return result
        except Exception as exc:
            logger.error(f"Failed to generate text: {exc}")
            raise

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
    ) -> dict:
        json_system = system_prompt
        if not json_system:
            json_system = "You are a helpful assistant that responds in valid JSON format."
        elif "json" not in json_system.lower():
            json_system += "\n\nYou must respond with valid JSON only. No markdown, no explanation, just pure JSON."

        raw = await self.generate(
            prompt=prompt,
            system_prompt=json_system,
            temperature=temperature,
            max_tokens=self.default_max_tokens,
        )

        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[len("```json"):]
        elif cleaned.startswith("```"):
            cleaned = cleaned[len("```"):]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-len("```")]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("LLM response was not valid JSON, attempting extraction")
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(cleaned[start:end])
                except json.JSONDecodeError:
                    pass
            start = cleaned.find("[")
            end = cleaned.rfind("]") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(cleaned[start:end])
                except json.JSONDecodeError:
                    pass
            logger.error(f"Could not parse JSON from LLM response: {raw[:500]}")
            raise ValueError(f"LLM did not return valid JSON: {raw[:200]}")

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        client = await self._get_client()
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.default_max_tokens,
            "stream": True,
        }

        delay = self._base_delay
        for attempt in range(self._max_retries):
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    timeout=httpx.Timeout(120.0, connect=30.0),
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[len("data: "):]
                        if data_str.strip() == "[DONE]":
                            return
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                return
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code == 429 or status_code >= 500:
                    logger.warning(
                        f"Stream error {status_code}, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self._max_retries})"
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 60.0)
                else:
                    raise
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                logger.warning(
                    f"Stream connection error: {exc}, retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{self._max_retries})"
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)

        raise RuntimeError("Max retries exceeded for streaming request")

    async def embed(self, text: str) -> List[float]:
        async def _request():
            client = await self._get_client()
            payload = {
                "model": "text-embedding-3-small",
                "input": text,
            }
            response = await client.post(
                f"{self.base_url}/embeddings",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]

        try:
            return await self._retry_request(_request)
        except Exception as exc:
            logger.error(f"Failed to generate embedding: {exc}")
            raise

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        batch_size = 64
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            async def _request(batch=batch):
                client = await self._get_client()
                payload = {
                    "model": "text-embedding-3-small",
                    "input": batch,
                }
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                sorted_data = sorted(data["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in sorted_data]

            try:
                batch_embeddings = await self._retry_request(_request)
                all_embeddings.extend(batch_embeddings)
            except Exception as exc:
                logger.error(f"Failed to generate batch embeddings: {exc}")
                raise

        return all_embeddings
