import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class AIInsightError(RuntimeError):
    """Raised when Gemini cannot return a usable insight response."""


AI_INSIGHT_PROMPT = """You are a concise finance analyst for a business expense platform.
Use only the approved-expense summary supplied by the backend. Never invent transactions.
Return valid JSON only with this exact shape:
{
  "summary": "one short business-friendly paragraph",
  "insights": ["2-4 concrete observations"],
  "warnings": ["0-3 material warnings"],
  "recommendations": ["0-3 practical next actions"]
}
Keep every list item under 24 words. Use amounts from the summary exactly when helpful."""


def _clean_list(value, limit):
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value[:limit] if str(item).strip()]


def _strip_markdown_json(text):
    cleaned = str(text or '').strip()
    if cleaned.startswith('```'):
        cleaned = cleaned.split('```', 2)[1]
        if cleaned.lower().startswith('json'):
            cleaned = cleaned[4:]
    return cleaned.strip()


def generate_ai_insight(snapshot):
    api_key = str(getattr(settings, 'GEMINI_API_KEY', '') or '').strip()
    model = str(
        getattr(settings, 'GEMINI_INSIGHTS_MODEL', 'gemini-2.5-flash')
        or 'gemini-2.5-flash'
    ).strip()
    if not api_key:
        raise AIInsightError('Gemini is not configured.')

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        logger.exception('google-genai is not installed')
        raise AIInsightError('Gemini is unavailable.') from exc

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=[AI_INSIGHT_PROMPT, json.dumps(snapshot, default=str)],
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type='application/json',
            ),
        )
    except Exception as exc:
        logger.warning('Gemini expense insights request failed', extra={'model': model})
        raise AIInsightError('Gemini request failed.') from exc

    try:
        insight = json.loads(_strip_markdown_json(getattr(response, 'text', '')))
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning('Gemini expense insights returned invalid JSON', extra={'model': model})
        raise AIInsightError('Gemini returned invalid JSON.') from exc

    summary = str(insight.get('summary') or '').strip()
    insights = _clean_list(insight.get('insights'), limit=4)
    if not summary or not insights:
        raise AIInsightError('Gemini returned an incomplete response.')

    return {
        'summary': summary,
        'insights': insights,
        'warnings': _clean_list(insight.get('warnings'), limit=3),
        'recommendations': _clean_list(insight.get('recommendations'), limit=3),
        'provider': 'gemini',
        'model': model,
    }
