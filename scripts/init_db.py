"""Initialize database schema (pgvector + tables)."""

from app.database import init_db


def main() -> None:
    init_db()
    print("Database initialized: pgvector extension + document_metadata table created.")


if __name__ == "__main__":
    main()
