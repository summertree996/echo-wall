import json
import asyncio
from typing import Any

import httpx

from app.core.config import get_settings


SUPPORTED_MODELS = {"deepseek-v4-flash", "deepseek-v4-pro"}
SUPPORTED_REASONING_EFFORTS = {"high", "max"}


class DeepSeekClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._semaphore = asyncio.Semaphore(max(1, self.settings.deepseek_max_concurrency))

    def configured(self) -> bool:
        return bool(self.settings.resolved_deepseek_key())

    def normalize_model(self, model: str | None) -> str:
        return model if model in SUPPORTED_MODELS else self.settings.deepseek_default_model

    def normalize_reasoning_effort(self, reasoning_effort: str | None) -> str:
        return reasoning_effort if reasoning_effort in SUPPORTED_REASONING_EFFORTS else "high"

    async def _chat_json(
        self,
        messages: list[dict[str, str]],
        model: str | None,
        thinking: bool | None,
        reasoning_effort: str | None,
        temperature: float = 0.2,
        max_tokens: int = 800,
        timeout_seconds: float | None = None,
        attempts: int = 2,
    ) -> dict[str, Any] | None:
        api_key = self.settings.resolved_deepseek_key()
        if not api_key:
            return None

        selected_model = self.normalize_model(model)
        thinking_enabled = self.settings.deepseek_default_thinking if thinking is None else thinking
        selected_effort = self.normalize_reasoning_effort(reasoning_effort)
        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": max_tokens,
            "thinking": {"type": "enabled" if thinking_enabled else "disabled"},
        }
        if thinking_enabled:
            payload["reasoning_effort"] = selected_effort

        content = await self._post_chat_completion(
            api_key=api_key,
            payload=payload,
            timeout_seconds=timeout_seconds or self.settings.deepseek_timeout_seconds,
            attempts=attempts,
        )
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None

    async def _post_chat_completion(
        self,
        *,
        api_key: str,
        payload: dict[str, Any],
        timeout_seconds: float,
        attempts: int,
    ) -> str:
        last_error: Exception | None = None
        total_attempts = max(1, attempts)
        for attempt in range(total_attempts):
            try:
                async with self._semaphore:
                    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                        response = await client.post(
                            f"{self.settings.deepseek_api_base}/chat/completions",
                            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                            json=payload,
                        )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code
                if status_code != 429 and status_code < 500:
                    raise
                if attempt >= total_attempts - 1:
                    raise
                await asyncio.sleep(self._retry_delay_seconds(exc.response, attempt))
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt >= total_attempts - 1:
                    raise
                await asyncio.sleep(min(1.0 + attempt, 2.0))
        if last_error:
            raise last_error
        raise RuntimeError("DeepSeek request failed")

    @staticmethod
    def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return min(max(float(retry_after), 0.2), 2.0)
            except ValueError:
                pass
        return min(1.0 + attempt, 2.0)

    async def test_connection(
        self,
        model: str | None = None,
        thinking: bool | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any] | None:
        data = await self._chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "你是 API 连通性检查器。只返回JSON。"
                        "示例JSON: {\"ok\": true, \"message\": \"ready\"}。"
                    ),
                },
                {"role": "user", "content": "请返回 ok=true 和简短中文 message。"},
            ],
            model,
            thinking,
            reasoning_effort,
            temperature=0,
            max_tokens=120,
            timeout_seconds=self.settings.deepseek_timeout_seconds,
            attempts=2,
        )
        if not data:
            return None
        return {
            "ok": bool(data.get("ok", True)),
            "message": str(data.get("message") or "DeepSeek 连接正常")[:120],
        }

    async def analyze_card(
        self,
        text: str,
        model: str | None = None,
        thinking: bool | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any] | None:
        data = await self._chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "你是反馈文本分析器。请用认知评价视角分析评论，关注评论者对价值、目标达成、"
                        "掌控感、公平感、信任、安全感、认知负荷和参与意愿的评价。只返回JSON，不要解释。"
                        "情绪规则: positive=主要表达认可、收益、支持、清晰感、掌控感、信任感、参与意愿或价值提升; "
                        "neutral=主要是事实描述、问题询问、低风险建议、条件性需求或信息不足; "
                        "negative=主要表达明显担忧、阻碍、不公平、不信任、安全风险、表达压力、失控感、"
                        "挫败感、认知负荷过高或参与意愿下降。"
                        "混合规则: 涉及安全、信任、公平、表达压力和明显阻碍时，优先识别为negative; "
                        "仅提到这些主题但语气中性、只是希望说明更清楚时，不必判为negative; "
                        "普通优化建议如果没有明显风险或负向体验，归为neutral; 信息不足时归为neutral并降低confidence。"
                        "topics规则: topics是从当前评论归纳出的低层语义码，不要使用固定业务主题词表; "
                        "返回1到3个中文短语，优先描述评论的核心对象、问题、需求或体验; "
                        "避免过泛词，如问题、建议、反馈、体验、系统。"
                        "字段: sentiment=positive|neutral|negative, confidence=0-100, topics=字符串数组1到3个, summary=一句话。"
                    ),
                },
                {"role": "user", "content": text[:1200]},
            ],
            "deepseek-v4-flash",
            False,
            "high",
            max_tokens=360,
            timeout_seconds=self.settings.deepseek_card_timeout_seconds,
            attempts=2,
        )
        if not data:
            return None
        sentiment = data.get("sentiment")
        if sentiment not in {"positive", "neutral", "negative"}:
            sentiment = "neutral"
        topics = data.get("topics") if isinstance(data.get("topics"), list) else []
        return {
            "sentiment": sentiment,
            "confidence": int(data.get("confidence") or 60),
            "topics": [str(topic)[:30] for topic in topics[:3]],
            "summary": str(data.get("summary") or "")[:200],
        }

    async def summarize_wall(
        self,
        wall_title: str,
        cards: list[dict[str, Any]],
        model: str | None = None,
        thinking: bool | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any] | None:
        if not cards:
            return {
                "overview": "当前还没有足够评论生成摘要。",
                "key_points": [],
                "risks": [],
                "representative_card_ids": [],
            }
        compact_cards = [
            {
                "id": card["id"],
                "text": str(card["text"])[:420],
                "sentiment": card.get("sentiment") or "unknown",
                "topics": card.get("topics") or [],
                "reactions": card.get("reactions") or 0,
            }
            for card in cards[:80]
        ]
        return await self._chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "你是反馈墙主持人的会后分析助手。请基于输入评论做归纳式主题分析，并用认知评价视角识别风险和参与信号。"
                        "只返回JSON。不要使用预设主题词表; 主题必须从当前墙的评论内容、单卡topics、情绪和反应数据中归纳。"
                        "合并语义相近的topics，形成少量清晰主题; 不同主题之间应有可解释边界。"
                        "每个key_points项应是一个归纳主题，不要只是复述单条评论。"
                        "每个risks项应说明它影响的是信任、公平、安全、掌控感、认知负荷或参与意愿中的哪类信号。"
                        "字段: overview=120字以内中文总结; key_points=数组最多4项，每项含title, summary, evidence_card_ids; "
                        "risks=数组最多3项，每项含title, severity=low|medium|high, summary, evidence_card_ids; "
                        "representative_card_ids=最值得主持人点开的卡片ID数组最多5个。"
                        "所有证据ID必须来自输入，不要编造ID。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"wall_title": wall_title, "cards": compact_cards}, ensure_ascii=False),
                },
            ],
            model,
            thinking,
            reasoning_effort,
            temperature=0.15,
            max_tokens=1800,
            timeout_seconds=self.settings.deepseek_summary_timeout_seconds,
            attempts=2,
        )


deepseek_client = DeepSeekClient()
