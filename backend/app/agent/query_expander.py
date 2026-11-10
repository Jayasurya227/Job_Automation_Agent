"""
Module: query_expander.py
Purpose: Step 1 Universal Semantic Query Expansion Engine for Multi-Portal Discovery.
         Dynamically generates industry-standard job title synonyms, domain clusters,
         and combined multi-keyword queries for ANY role (AI, Frontend, Backend, Data, DevOps, etc.).
Standards: Rule 1 (Zero Hardcoding / 100% Dynamic Multi-User),
           Rule 2 (Pydantic Schema Validation),
           Rule 5 (Production Standard with In-Memory & Disk Caching).
"""
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.config import DEFAULT_MODEL, claude_client, BASE_DIR
from app.agent.llm import response_text, parse_json_object
from app.utils.rate_limiter import execute_with_rate_limit

logger = logging.getLogger("agent.query_expander")

CACHE_FILE = BASE_DIR / "backend" / "data" / "query_expansion_cache.json"
if not CACHE_FILE.parent.exists():
    CACHE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "query_expansion_cache.json"

_IN_MEMORY_CACHE: Dict[str, Dict[str, Any]] = {}


class RoleCluster(BaseModel):
    """Normalized search cluster for an arbitrary user target role."""
    primary_role: str = Field(..., description="The user's original target role input")
    domain_category: str = Field(..., description="Universal technical or professional domain (e.g. ai_ml, frontend, backend, data, devops, design, etc.)")
    search_synonyms: List[str] = Field(default_factory=list, description="Top 3 to 4 industry equivalent job titles used by HR recruiters")
    combined_query: str = Field(..., description="Unified comma-separated keyword query for native portal search (e.g. 'AI Engineer, Gen AI, Machine Learning')")


def _load_cache() -> None:
    """Loads cached role expansions from disk into memory."""
    global _IN_MEMORY_CACHE
    if not _IN_MEMORY_CACHE and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _IN_MEMORY_CACHE = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load query expansion cache: {e}")
            _IN_MEMORY_CACHE = {}


def _save_cache() -> None:
    """Persists memory cache to disk."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_IN_MEMORY_CACHE, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save query expansion cache: {e}")


def _fallback_expand_role(role: str) -> RoleCluster:
    """
    Robust zero-token algorithmic fallback if network/LLM is offline.
    Never hardcoded to any specific candidate or tool.
    """
    clean_role = role.strip()
    words = clean_role.split()
    synonyms = [clean_role]

    role_lower = clean_role.lower()

    # Generic title level interchange
    if "developer" in role_lower:
        synonyms.append(re.sub(r"\bdeveloper\b", "Engineer", clean_role, flags=re.IGNORECASE))
    elif "engineer" in role_lower:
        synonyms.append(re.sub(r"\bengineer\b", "Developer", clean_role, flags=re.IGNORECASE))

    if "junior" not in role_lower and "senior" not in role_lower and "lead" not in role_lower:
        synonyms.append(f"Associate {clean_role}")

    # Deduplicate preserving order
    seen = set()
    deduped = []
    for s in synonyms:
        s_clean = s.strip()
        if s_clean.lower() not in seen:
            seen.add(s_clean.lower())
            deduped.append(s_clean)

    # Combined query string
    combined = ", ".join(deduped[:3])

    domain = "general_tech"
    if any(k in role_lower for k in ["ai", "ml", "learning", "gpt", "llm", "neural"]):
        domain = "ai_ml"
    elif any(k in role_lower for k in ["front", "react", "ui", "web", "css", "vue", "angular"]):
        domain = "frontend"
    elif any(k in role_lower for k in ["back", "python", "node", "api", "django", "fastapi", "golang", "java"]):
        domain = "backend"
    elif any(k in role_lower for k in ["data", "sql", "analytics", "bi", "tableau", "powerbi"]):
        domain = "data"
    elif any(k in role_lower for k in ["devops", "cloud", "aws", "docker", "kubernetes", "sre"]):
        domain = "devops"

    return RoleCluster(
        primary_role=clean_role,
        domain_category=domain,
        search_synonyms=deduped[:4],
        combined_query=combined
    )


def expand_target_role(role: str, model_name: str = DEFAULT_MODEL) -> RoleCluster:
    """
    100% Dynamic Semantic Role Expansion using Claude Brain.
    Takes any role (e.g. 'AI Engineer', 'React Developer', 'Data Analyst', 'DevOps')
    and returns industry synonyms and a combined native query.
    Cached for < 1ms response on subsequent runs.
    """
    if not role or not role.strip():
        return RoleCluster(primary_role="", domain_category="general", search_synonyms=[], combined_query="")

    clean_role = role.strip()
    cache_key = clean_role.lower()

    _load_cache()
    if cache_key in _IN_MEMORY_CACHE:
        try:
            return RoleCluster(**_IN_MEMORY_CACHE[cache_key])
        except Exception:
            pass

    # Prompt Claude for dynamic industry recruitment synonyms
    system_instruction = (
        "You are an expert technical recruitment taxonomist and search query architect.\n"
        "Your task is to take any given target job role entered by a candidate (from ANY domain: software, AI, frontend, data, devops, design, operations, etc.) "
        "and return the top 3-4 industry-standard job title synonyms that hiring managers and recruiters actually use on job boards (Naukri, Indeed, LinkedIn) "
        "for the exact same core skillset.\n\n"
        "Guidelines:\n"
        "1. Include variations with common seniority qualifiers (e.g. Associate, Junior) or common alternate titles (e.g. Developer vs Engineer vs Specialist).\n"
        "2. In 'combined_query', provide a clean, concise, comma-separated list of the 3 most effective keywords for portal search bars.\n"
        "3. Categorize into a clean normalized 'domain_category' (e.g. 'ai_ml', 'frontend', 'backend', 'data_analytics', 'cloud_devops', 'mobile', 'qa_testing', 'general').\n"
        "4. Output strictly a JSON object conforming to the schema.\n"
    )

    prompt = (
        f"Target Job Role: \"{clean_role}\"\n\n"
        "Respond with a pure JSON object matching this schema:\n"
        f"{json.dumps(RoleCluster.model_json_schema())}"
    )

    try:
        response = execute_with_rate_limit(
            claude_client.messages.create,
            model=model_name,
            max_tokens=400,
            system=system_instruction,
            messages=[{"role": "user", "content": prompt}],
        )

        data = parse_json_object(response_text(response))
        # Ensure primary_role matches exactly
        data["primary_role"] = clean_role
        cluster = RoleCluster(**data)

        # Store in cache
        _IN_MEMORY_CACHE[cache_key] = cluster.model_dump()
        _save_cache()
        return cluster

    except Exception as err:
        logger.warning(f"Claude query expansion failed for '{clean_role}' ({err}). Using dynamic algorithmic fallback.")
        fallback = _fallback_expand_role(clean_role)
        _IN_MEMORY_CACHE[cache_key] = fallback.model_dump()
        _save_cache()
        return fallback


def expand_multiple_roles(roles: List[str]) -> List[RoleCluster]:
    """
    Expands a list of user target roles and groups them by domain category
    so different domains (e.g. Frontend vs AI) can be searched in sequential slots
    without confusing portal search engines.
    """
    clusters: List[RoleCluster] = []
    seen_roles = set()

    for r in roles:
        if not r or not r.strip():
            continue
        r_clean = r.strip()
        if r_clean.lower() in seen_roles:
            continue
        seen_roles.add(r_clean.lower())
        clusters.append(expand_target_role(r_clean))

    return clusters

