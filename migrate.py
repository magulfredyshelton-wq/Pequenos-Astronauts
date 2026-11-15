from psycopg import OperationalError

from app.db import migrar


if __name__ == "__main__":
    try:
        versoes = migrar()
    except OperationalError:
        raise SystemExit("Não foi possível ligar ao PostgreSQL. Confirma o serviço e ASTRO_DATABASE_URL.") from None
    print("Migrações PostgreSQL:", ", ".join(versoes) if versoes else "já aplicadas")
