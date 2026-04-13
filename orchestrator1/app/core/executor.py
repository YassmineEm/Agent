import json
import asyncio
from app.services.agents_client import call_agent
from app.utils.logger import get_logger

log = get_logger(__name__)


def _inject_context(sub_question: str, context: list[dict]) -> str:
    """
    Remplace {agent_result} par la vraie réponse de l'agent.
    Ex: "fuel pour {sql_result}" → "fuel pour Airbus A340, Boeing 737"
    """
    for result in context:
        if not result.get("_success"):
            continue
        agent  = result.get("agent", "")
        if result.get("agent") == "sql":
            rows = result.get("rows") or result.get("metadata", {}).get("rows", [])

            if rows:
                formatted = []

                for row in rows:
                    # prend toutes les colonnes dynamiquement
                    values = [str(v) for v in row.values() if v is not None]
                    if values:
                        formatted.append(", ".join([f"{k}: {v}" for k, v in row.items()]))

                answer = ", ".join(formatted)

            else:
                answer = str(result.get("answer", ""))
        else:
            answer = str(result.get("answer", ""))

        if len(answer) > 500:
            answer = answer[:500] + "..."

        placeholder  = f"{{{agent}_result}}"
        sub_question = sub_question.replace(placeholder, answer)

    return sub_question


def _parse_stations_from_sql(answer) -> list:
    """
    Tente d'extraire une liste de stations depuis la réponse SQL.
    La réponse SQL peut être une liste de dicts ou une string JSON.
    """
    if isinstance(answer, list):
        return answer
    if isinstance(answer, str):
        try:
            parsed = json.loads(answer)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return []


# Champs possibles pour chaque attribut Station attendu par location_agent
_NAME_ALIASES = [
    "name", "nom", "station_name", "station", "libelle", "label", "title",
    "nom_station_fr", "nom_station", "station_fr", "nom_fr"
]

_LAT_ALIASES = [
    "lat", "latitude", "lat_gps", "geo_lat", "y"
]

_LNG_ALIASES = [
    "lng", "lon", "longitude", "lng_gps", "geo_lng", "long", "x"
]

_ADDR_ALIASES = [
    "address", "adresse", "addr", "city", "location",
    "ville", "address_fr", "address_ar"
]

_FUEL_ALIASES = [
    "fuel_type", "carburant", "type_carburant", "fuel", "product",
    "type", "produit", "code_produit", "prix", "price"
]

def _normalize_station_row(row: dict) -> dict | None:
    """
    Remappe un dict SQL vers le format attendu par le location_agent :
    { name, lat, lng, address?, fuel_type? }
    Retourne None si lat/lng introuvables.
    """
    def _pick(d, aliases):
        for key in aliases:
            for k, v in d.items():
                if k.lower() == key.lower() and v is not None:
                    return v
        return None

    name = _pick(row, _NAME_ALIASES) or "Station AKWA"
    lat  = _pick(row, _LAT_ALIASES)
    lng  = _pick(row, _LNG_ALIASES)

    if lat is None or lng is None:
        return None   # ligne inutilisable

    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return None

    station = {"name": str(name), "lat": lat, "lng": lng}

    addr = _pick(row, _ADDR_ALIASES)
    if addr:
        station["address"] = str(addr)

    fuel = _pick(row, _FUEL_ALIASES)
    if fuel:
        station["fuel_type"] = str(fuel)

    return station


def _build_extra(agent: str, context: list[dict], geo: dict | None) -> dict:
    if agent != "location":
        return {}

    extra = {}

    if geo:
        extra["lat"] = geo.get("lat", 0.0)
        extra["lng"] = geo.get("lng", 0.0)

    for result in context:
        if result.get("agent") == "sql" and result.get("_success"):

            rows = result.get("metadata", {}).get("rows", [])
            if not rows:
                rows = result.get("rows", [])
            if not rows:
                rows = _parse_stations_from_sql(result.get("answer", ""))

            if rows:
                normalized = [_normalize_station_row(r) for r in rows]
                stations   = [s for s in normalized if s is not None]

                if stations:
                    extra["stations"] = stations
                    log.info(
                        "Stations normalisées pour location agent",
                        nb_total=len(rows),
                        nb_valides=len(stations),
                        exemple=stations[0] if stations else {},
                    )
                else:
                    log.warning(
                        "Rows SQL présentes mais aucune station valide après remapping",
                        sample_keys=list(rows[0].keys()) if rows else [],
                    )
            else:
                log.warning("Aucune station extraite du résultat SQL")
            break

    return extra


async def _run_step(
    step:       dict,
    chatbot_id: str,
    context:    list[dict],
    geo:        dict | None = None,
    language:   str         = "fr",
) -> list[dict]:
    """Exécute un step — peut contenir 1 ou N agents."""
    tasks = []
    for agent, sub_q in step.items():
        enriched_q = _inject_context(sub_q, context)
        if enriched_q != sub_q:
            log.info(
                "Context injecté",
                agent=agent,
                enriched=enriched_q[:80],
            )

        extra = _build_extra(agent, context, geo)

        log.info(
            "Question envoyée",
            agent=agent,
            question=enriched_q[:80],
            has_extra=bool(extra),
        )
        tasks.append(call_agent(agent, enriched_q, chatbot_id, extra=extra, language=language,))

    return list(await asyncio.gather(*tasks))


async def execute(
    plan:       dict,
    chatbot_id: str        = "",
    geo:        dict | None = None,     # ← {"lat": 33.5, "lng": -7.6} depuis main
    language:   str         = "fr",
) -> list[dict]:
    """
    Exécute le plan selon sa stratégie.

    plan = {
        "strategy": "parallel" | "sequential",
        "steps":    [{"agent": "question"}, ...]
    }
    """
    strategy = plan.get("strategy", "parallel")
    steps    = plan.get("steps", [])

    # Compatibilité avec l'ancien format {agent: question} sans strategy
    if not steps:
        steps    = [plan]
        strategy = "parallel"

    all_results: list[dict] = []

    if strategy == "parallel":
        # Chaque step est exécuté indépendamment en parallèle
        tasks = [_run_step(step, chatbot_id, [], geo) for step in steps]
        results_list = await asyncio.gather(*tasks)
        for results in results_list:
            all_results.extend(results)
        log.info("Exécution PARALLEL", nb_steps=len(steps))

    elif strategy == "sequential":
        # Étape par étape — contexte accumulé entre chaque step
        context: list[dict] = []

        for i, step in enumerate(steps):
            agent_name = list(step.keys())[0]
            log.info(
                "Exécution SEQUENTIAL",
                step=f"{i + 1}/{len(steps)}",
                agent=agent_name,
            )

            results = await _run_step(step, chatbot_id, context, geo)
            context.extend(results)
            all_results.extend(results)

            # Arrêter si l'étape échoue — inutile de continuer
            if not any(r.get("_success") for r in results):
                log.warning(
                    "Étape séquentielle échouée — arrêt de la séquence",
                    step=i + 1,
                    agent=agent_name,
                )
                break

    successful = sum(1 for r in all_results if r.get("_success"))
    log.info(
        "Exécution terminée",
        strategy=strategy,
        total=len(all_results),
        successful=successful,
        failed=len(all_results) - successful,
    )
    return all_results