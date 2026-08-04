from openai import OpenAI
import json
import math
import os
import re
from pathlib import Path
from typing import Optional


def resolve_openai_api_key(api_key: Optional[str] = None) -> Optional[str]:
    """Resolve OpenAI credentials from explicit arg, env vars, Streamlit secrets, or local files."""
    if api_key:
        return str(api_key)

    for env_name in ("OPENAI_API_KEY", "OPENAI_ADMIN_KEY"):
        value = os.getenv(env_name)
        if value:
            return str(value)

    try:
        import streamlit as st
    except Exception:
        st = None

    if st is not None:
        for secret_name in ("OPENAI_API_KEY", "OPENAI_ADMIN_KEY"):
            value = st.secrets.get(secret_name)
            if value:
                return str(value)

    repo_root = Path(__file__).resolve().parent.parent
    for path in [repo_root / ".streamlit" / "secrets.toml", repo_root / "apikey"]:
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for key_name in ("OPENAI_API_KEY", "OPENAI_ADMIN_KEY"):
            match = re.search(rf'^{key_name}\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if match:
                return match.group(1).strip()

    return None


def check_safe(text: str, api_key: Optional[str] = None) -> dict:
    """Call OpenAI Moderation API and return a simple result dict.

    Returns:
      - {'flagged': bool, 'categories': dict, 'scores': dict} on success
      - {'error': '...'} on failure
    """
    try:
        resolved_key = resolve_openai_api_key(api_key)
        if not resolved_key:
            return {"error": "Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable."}
        client = OpenAI(api_key=resolved_key)
        resp = client.moderations.create(model="omni-moderation-latest", input=text)

        # resp may be a dict-like or an object with attributes depending on client
        if isinstance(resp, dict):
            results = resp.get("results") or []
        else:
            results = getattr(resp, "results", []) or []

        if not results:
            return {"flagged": False, "categories": {}, "scores": {}}

        r = results[0]

        # extract values robustly from either mapping or object
        if isinstance(r, dict):
            flagged = bool(r.get("flagged", False))
            categories = r.get("categories", {}) or {}
            scores = r.get("category_scores", {}) or {}
        else:
            flagged = bool(getattr(r, "flagged", False))
            cat = getattr(r, "categories", None)
            if cat is None:
                categories = {}
            else:
                try:
                    categories = dict(cat)
                except Exception:
                    try:
                        categories = cat.__dict__
                    except Exception:
                        categories = {"raw": str(cat)}

            sc = getattr(r, "category_scores", None) or getattr(r, "scores", None)
            if sc is None:
                scores = {}
            else:
                try:
                    scores = dict(sc)
                except Exception:
                    try:
                        scores = sc.__dict__
                    except Exception:
                        scores = {"raw": str(sc)}

        return {"flagged": flagged, "categories": categories, "scores": scores}
    except Exception as e:
        return {"error": str(e)}


def check_relevance(text: str, api_key: Optional[str] = None) -> dict:
    """Use an LLM to decide whether `text` is an answer to a law essay question.

    Returns:
      - {'is_answer': True/False, 'reason': '...'} or {'error': '...'}
    """
    prompt = (
        "你是一個分類器：判斷下列文字是否為針對法律申論題的學生作答。"
        " 僅回傳一個 JSON 物件，格式為 {\"is_answer\": true|false, \"reason\": \"說明理由\"}，"
        " 並且不要多餘的文字。\n\n輸入文字：\n"
    )
    try:
        resolved_key = resolve_openai_api_key(api_key)
        if not resolved_key:
            return {"error": "Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable."}
        client = OpenAI(api_key=resolved_key)
        resp = client.responses.create(model="gpt-4o-mini", input=prompt + text, temperature=0)

        # extract text robustly
        out = None
        if isinstance(resp, dict):
            out = resp.get("output_text") or resp.get("output", None)
            if isinstance(out, list) and out:
                try:
                    out = out[0].get("content", [{}])[0].get("text")
                except Exception:
                    out = str(out)
        else:
            out = getattr(resp, "output_text", None) or getattr(resp, "output", None) or str(resp)
            if not isinstance(out, str) and isinstance(out, list) and out:
                try:
                    out = out[0].content[0].text
                except Exception:
                    out = str(out)

        if not out or not isinstance(out, str):
            return {"error": "empty response from model"}

        # try parse JSON
        try:
            parsed = json.loads(out.strip())
            return {"is_answer": bool(parsed.get("is_answer")), "reason": parsed.get("reason", "")}
        except Exception:
            # fallback: look for yes/no
            low = out.lower()
            if "true" in low or "yes" in low or "是" in low:
                return {"is_answer": True, "reason": out.strip()}
            if "false" in low or "no" in low or "不是" in low:
                return {"is_answer": False, "reason": out.strip()}
            return {"error": "cannot parse model response", "raw": out}
    except Exception as e:
        return {"error": str(e)}


def check_ai_generated(text: str, api_key: Optional[str] = None) -> dict:
    """Use an LLM to decide whether `text` is likely AI-generated legal essay content.

    Returns:
      - {'is_ai_generated': True/False, 'confidence': 0.0-1.0, 'reason': '...'}
      - {'error': '...'} on failure
    """
    prompt = (
        "你是台灣法律申論作答的 AI 審查分類器。"
        " 請用『嚴格度 6/10（略嚴）』判斷下列文字是否疑似 AI 生成、代寫或經 AI 大幅改寫。"
        " 你有三個校正基準："
        " (A) 兩份真人樣本：可有錯字、編號混用、跳接、推理修正、段落不均，不能因文筆好就判 AI；"
        " (B) 一份 AI 樣本：高度模板化、段落過度對稱、通用術語密集、可替換人名事實後仍成立。"
        " 審查規則："
        " 1) 文筆流暢、結構完整、法條引用清楚只能算弱訊號，不能單獨定罪；"
        " 2) 強訊號：模板可移植性高、事實互動薄弱且套話密集、台灣法條/法學概念錯置；"
        " 3) 中訊號：語氣過度均質、段落過度對稱、結論先行後機械展開；"
        " 4) 人類保護訊號：自然錯漏、推理轉折、局部不一致、不平均展開，應降低 AI 風險；"
        " 5) 若只有弱訊號或證據不足，偏向 false。"
        " 請先在內部完成風險判斷後再輸出，且只輸出 JSON，不得有其他文字。"
        " JSON 格式固定為："
        " {\"is_ai_generated\": true|false, \"confidence\": 0到1之間數字, \"risk_level\": \"low|medium|high\", \"reason\": \"一句話\", \"reasons\": [\"最多3點\"]}。"
        "\n\n輸入文字：\n"
    )
    try:
        resolved_key = resolve_openai_api_key(api_key)
        if not resolved_key:
            return {"error": "Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable."}
        client = OpenAI(api_key=resolved_key)
        resp = client.responses.create(model="gpt-4o-mini", input=prompt + text, temperature=0)

        out = None
        if isinstance(resp, dict):
            out = resp.get("output_text") or resp.get("output", None)
            if isinstance(out, list) and out:
                try:
                    out = out[0].get("content", [{}])[0].get("text")
                except Exception:
                    out = str(out)
        else:
            out = getattr(resp, "output_text", None) or getattr(resp, "output", None) or str(resp)
            if not isinstance(out, str) and isinstance(out, list) and out:
                try:
                    out = out[0].content[0].text
                except Exception:
                    out = str(out)

        if not out or not isinstance(out, str):
            return {"error": "empty response from model"}

        try:
            parsed = json.loads(out.strip())
            confidence = parsed.get("confidence", 0)
            try:
                confidence = float(confidence)
            except Exception:
                confidence = 0.0
            confidence = max(0.0, min(1.0, confidence))
            reason = parsed.get("reason", "")
            if not reason and isinstance(parsed.get("reasons"), list) and parsed.get("reasons"):
                reason = "；".join(str(x) for x in parsed.get("reasons")[:3])
            return {
                "is_ai_generated": bool(parsed.get("is_ai_generated")),
                "confidence": confidence,
                "reason": reason,
            }
        except Exception:
            low = out.lower()
            if "true" in low or "yes" in low or "是" in low or "ai" in low:
                return {"is_ai_generated": True, "confidence": 0.5, "reason": out.strip()}
            if "false" in low or "no" in low or "不是" in low:
                return {"is_ai_generated": False, "confidence": 0.5, "reason": out.strip()}
            return {"error": "cannot parse model response", "raw": out}
    except Exception as e:
        return {"error": str(e)}


def get_embedding(text: str, api_key: Optional[str] = None) -> dict:
    """Return embedding vector for `text` using OpenAI embeddings API."""
    try:
        resolved_key = resolve_openai_api_key(api_key)
        if not resolved_key:
            return {"error": "Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable."}
        client = OpenAI(api_key=resolved_key)
        resp = client.embeddings.create(model="text-embedding-3-small", input=text)
        # resp.data is usually a list with one item containing embedding
        emb = None
        if isinstance(resp, dict):
            data = resp.get("data") or []
            if data:
                emb = data[0].get("embedding")
        else:
            data = getattr(resp, "data", None)
            if data and len(data) > 0:
                first = data[0]
                emb = getattr(first, "embedding", None) or (first.get("embedding") if isinstance(first, dict) else None)
        if emb is None:
            return {"error": "no embedding returned"}
        return {"embedding": emb}
    except Exception as e:
        return {"error": str(e)}


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def find_embedding_duplicate(text: str, answers: list[dict], api_key: Optional[str] = None, threshold: float = 0.92) -> Optional[dict]:
    """Return an existing answer dict if embedding similarity >= threshold."""
    if not text or not answers:
        return None
    emb_result = get_embedding(text, api_key=api_key)
    if "error" in emb_result:
        return {"error": emb_result["error"]}
    emb = emb_result["embedding"]
    for ans in answers:
        existing = (ans.get("answer_text") or "").strip()
        if not existing:
            continue
        e_res = get_embedding(existing, api_key=api_key)
        if "error" in e_res:
            continue
        sim = cosine_similarity(emb, e_res["embedding"])
        if sim >= threshold:
            return {"answer": ans, "score": sim}
    return None
