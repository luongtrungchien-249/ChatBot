-- pg_dump/pg_restore use a restricted search_path. SQL functions invoked by
-- generated columns must resolve both the function and its dictionary explicitly.
-- Preserve the existing function identity and generated data; do not rewrite old migrations.
CREATE OR REPLACE FUNCTION public.vn_tsv(t text) RETURNS tsvector
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $fn$
  SELECT pg_catalog.to_tsvector(
    'pg_catalog.simple'::pg_catalog.regconfig,
    public.unaccent('public.unaccent'::pg_catalog.regdictionary, t)
  )
$fn$;

-- IMMUTABLE is an application promise: keep the unaccent dictionary unchanged.
-- A dictionary change requires rebuilding stored tsv values as well as their GIN index.
