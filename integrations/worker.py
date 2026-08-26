from datetime import datetime, timezone

from .providers import ProviderNotConfigured, get_provider


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_provider(name: str, enabled: bool = False) -> dict:
    """Run one approved provider boundary without making silent fallback data."""
    started_at = utc_now()
    try:
        adapter = get_provider(name, enabled=enabled)
        records = list(adapter.fetch())
        return {'provider': name, 'status': 'completed', 'started_at': started_at,
                'completed_at': utc_now(), 'item_count': len(records), 'records': records}
    except ProviderNotConfigured as exc:
        return {'provider': name, 'status': 'not_configured', 'started_at': started_at,
                'completed_at': utc_now(), 'item_count': 0, 'error_summary': str(exc)}
