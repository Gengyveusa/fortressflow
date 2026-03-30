"""Multi-lingual and localisation support for FortressFlow."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

SUPPORTED_LOCALES = {
    "en": {"name": "English", "direction": "ltr", "date_format": "%m/%d/%Y"},
    "es": {"name": "Español", "direction": "ltr", "date_format": "%d/%m/%Y"},
    "fr": {"name": "Français", "direction": "ltr", "date_format": "%d/%m/%Y"},
    "de": {"name": "Deutsch", "direction": "ltr", "date_format": "%d.%m.%Y"},
    "pt": {"name": "Português", "direction": "ltr", "date_format": "%d/%m/%Y"},
    "ja": {"name": "日本語", "direction": "ltr", "date_format": "%Y/%m/%d"},
    "zh": {"name": "中文", "direction": "ltr", "date_format": "%Y/%m/%d"},
    "ko": {"name": "한국어", "direction": "ltr", "date_format": "%Y/%m/%d"},
    "ar": {"name": "العربية", "direction": "rtl", "date_format": "%d/%m/%Y"},
    "hi": {"name": "हिन्दी", "direction": "ltr", "date_format": "%d/%m/%Y"},
}


@dataclass
class TranslatedContent:
    id: str = field(default_factory=lambda: str(uuid4()))
    original_locale: str = "en"
    original_text: str = ""
    translations: dict[str, str] = field(default_factory=dict)
    content_type: str = "email"  # email, social_post, template, kb_article, landing_page
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    quality_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class LocaleConfig:
    locale: str = "en"
    timezone: str = "UTC"
    currency: str = "USD"
    number_format: str = "#,###.##"
    date_format: str = "%m/%d/%Y"


class I18nService:
    """Handles multi-lingual content and localisation."""

    def __init__(self):
        self._content_store: dict[str, TranslatedContent] = {}
        self._user_locales: dict[str, LocaleConfig] = {}
        self._translation_memory: dict[str, dict[str, str]] = {}  # source_hash -> {locale: translation}

    async def translate_content(
        self,
        text: str,
        source_locale: str,
        target_locales: list[str],
        content_type: str = "email",
        api_key: Optional[str] = None,
    ) -> TranslatedContent:
        """Translate content to multiple locales using AI."""
        content = TranslatedContent(original_locale=source_locale, original_text=text, content_type=content_type)
        for locale in target_locales:
            if locale not in SUPPORTED_LOCALES:
                continue
            if locale == source_locale:
                content.translations[locale] = text
                content.quality_scores[locale] = 1.0
                continue
            # AI translation via Groq
            try:
                if api_key:
                    from groq import AsyncGroq

                    client = AsyncGroq(api_key=api_key)
                    locale_info = SUPPORTED_LOCALES[locale]
                    response = await client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[
                            {
                                "role": "system",
                                "content": f"You are a professional translator. Translate the following {content_type} content from {SUPPORTED_LOCALES[source_locale]['name']} to {locale_info['name']}. Preserve formatting, tone, and cultural nuances. Adapt idioms and references for the target culture. Return ONLY the translation.",
                            },
                            {"role": "user", "content": text},
                        ],
                        temperature=0.3,
                        max_tokens=4096,
                    )
                    content.translations[locale] = (response.choices[0].message.content or "").strip()
                    content.quality_scores[locale] = 0.85
                else:
                    content.translations[locale] = f"[{locale}] {text}"
                    content.quality_scores[locale] = 0.0
            except Exception as e:
                logger.error("Translation to %s failed: %s", locale, e)
                content.translations[locale] = f"[{locale}] {text}"
                content.quality_scores[locale] = 0.0
        self._content_store[content.id] = content
        return content

    def get_supported_locales(self) -> dict:
        return SUPPORTED_LOCALES

    def set_user_locale(self, user_id: str, locale: str, timezone: str = "UTC", currency: str = "USD") -> LocaleConfig:
        if locale not in SUPPORTED_LOCALES:
            locale = "en"
        config = LocaleConfig(
            locale=locale, timezone=timezone, currency=currency, date_format=SUPPORTED_LOCALES[locale]["date_format"]
        )
        self._user_locales[user_id] = config
        return config

    def get_user_locale(self, user_id: str) -> LocaleConfig:
        return self._user_locales.get(user_id, LocaleConfig())

    def format_date(self, dt: datetime, locale: str = "en") -> str:
        fmt = SUPPORTED_LOCALES.get(locale, {}).get("date_format", "%m/%d/%Y")
        return dt.strftime(fmt)

    def get_content_translations(self, content_id: str) -> Optional[TranslatedContent]:
        return self._content_store.get(content_id)

    def get_translation_stats(self) -> dict:
        total = len(self._content_store)
        locale_counts: dict[str, int] = {}
        avg_quality: dict[str, list[float]] = {}
        for c in self._content_store.values():
            for locale, score in c.quality_scores.items():
                locale_counts[locale] = locale_counts.get(locale, 0) + 1
                avg_quality[locale] = avg_quality.get(locale, [])
                avg_quality[locale].append(score)
        return {
            "total_content_items": total,
            "translations_by_locale": locale_counts,
            "avg_quality_by_locale": {k: round(sum(v) / len(v), 2) for k, v in avg_quality.items() if v},
            "supported_locales": list(SUPPORTED_LOCALES.keys()),
        }
