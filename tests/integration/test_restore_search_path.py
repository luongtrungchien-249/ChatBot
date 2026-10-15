from infra.db import transaction


async def test_generated_tsv_survives_pg_restore_restricted_search_path(
    postgres_san_sang: None,
) -> None:
    async with transaction() as connection:
        expected = await connection.fetchval("SELECT public.vn_tsv('Nghỉ phép năm')::text")
        await connection.execute("SET LOCAL search_path = pg_catalog")
        assert await connection.fetchval("SELECT public.vn_tsv('Nghỉ phép năm')::text") == expected
        await connection.execute(
            """CREATE TEMP TABLE restore_tsv_test (
                 text text, tsv tsvector GENERATED ALWAYS AS (public.vn_tsv(text)) STORED
               ) ON COMMIT DROP"""
        )
        await connection.execute("INSERT INTO restore_tsv_test(text) VALUES('Nghỉ phép năm')")
        assert await connection.fetchval("SELECT tsv::text FROM restore_tsv_test") == expected
