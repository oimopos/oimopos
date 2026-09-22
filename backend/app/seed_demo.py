from __future__ import annotations

import argparse
import json

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import get_settings
from .demo_data import build_buffet_demo_state, demo_state_summary


def seed(tenant_slug: str) -> dict[str, object]:
    settings = get_settings()
    with connect(settings.database_url, row_factory=dict_row) as connection:
        with connection.transaction():
            row = connection.execute(
                """
                SELECT tenant.id AS tenant_id, tenant.name, workspace.version, workspace.payload,
                       owner.id AS owner_id, owner.login AS owner_login
                FROM tenants tenant
                JOIN operational_state workspace ON workspace.tenant_id = tenant.id
                JOIN auth_users owner ON owner.tenant_id = tenant.id AND owner.role = 'owner' AND owner.is_active
                WHERE lower(tenant.slug) = lower(%s)
                ORDER BY owner.id
                LIMIT 1
                FOR UPDATE OF workspace
                """,
                (tenant_slug,),
            ).fetchone()
            if not row:
                raise SystemExit(f"Аккаунт с кодом {tenant_slug!r} не найден")
            state = build_buffet_demo_state(row["payload"])
            version = int(row["version"]) + 1
            connection.execute(
                "UPDATE operational_state SET version = %s, payload = %s, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = %s",
                (version, Jsonb(state), row["tenant_id"]),
            )
            connection.execute(
                """
                INSERT INTO operational_events
                  (tenant_id, state_version, actor_user_id, actor_login, actor_role, branch_id,
                   action, entity_type, entity_id, payload)
                VALUES (%s, %s, %s, %s, 'owner', NULL, 'demo.seed', 'workspace', %s, %s)
                """,
                (row["tenant_id"], version, row["owner_id"], row["owner_login"], row["tenant_id"], Jsonb(demo_state_summary(state))),
            )
    return {"tenant": row["name"], "slug": tenant_slug, "version": version, **demo_state_summary(state)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill one existing tenant with a complete buffet demo workspace")
    parser.add_argument("--tenant-slug", required=True)
    args = parser.parse_args()
    print(json.dumps(seed(args.tenant_slug), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
