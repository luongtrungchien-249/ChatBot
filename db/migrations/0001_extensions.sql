CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Boc unaccent thanh IMMUTABLE de dung duoc trong generated column.
-- Dang 2 tham so (chi dinh ro dictionary) moi immutable; dang 1 tham so thi khong.
-- Neu doi dictionary sau nay, phai REINDEX cac index GIN phu thuoc.
CREATE OR REPLACE FUNCTION vn_tsv(t text) RETURNS tsvector
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $fn$
  SELECT to_tsvector('simple', unaccent('unaccent', t))
$fn$;
