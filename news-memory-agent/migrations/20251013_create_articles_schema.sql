BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.articles (
    id BIGINT PRIMARY KEY
);

ALTER TABLE public.articles ALTER COLUMN id TYPE BIGINT;

ALTER TABLE public.articles
    ADD COLUMN IF NOT EXISTS url TEXT,
    ADD COLUMN IF NOT EXISTS title TEXT,
    ADD COLUMN IF NOT EXISTS content TEXT,
    ADD COLUMN IF NOT EXISTS summary TEXT,
    ADD COLUMN IF NOT EXISTS metadata JSONB,
    ADD COLUMN IF NOT EXISTS embedding vector(768),
    ADD COLUMN IF NOT EXISTS analyzed BOOLEAN,
    ADD COLUMN IF NOT EXISTS source_id BIGINT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

ALTER TABLE public.articles ALTER COLUMN metadata SET DEFAULT '{}'::jsonb;
ALTER TABLE public.articles ALTER COLUMN analyzed SET DEFAULT FALSE;
ALTER TABLE public.articles ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE public.articles ALTER COLUMN updated_at SET DEFAULT now();

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'articles'
          AND column_name = 'metadata'
          AND data_type <> 'jsonb'
    ) THEN
        ALTER TABLE public.articles
            ALTER COLUMN metadata TYPE JSONB USING metadata::jsonb;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'articles'
          AND column_name = 'embedding'
          AND (data_type <> 'USER-DEFINED' OR udt_name <> 'vector')
    ) THEN
        ALTER TABLE public.articles
            ALTER COLUMN embedding TYPE vector(768)
            USING (embedding::vector);
    END IF;
END
$$;

CREATE SEQUENCE IF NOT EXISTS public.articles_id_seq;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'articles'
          AND column_name = 'id'
          AND column_default LIKE 'nextval%articles_id_seq%'
    ) THEN
        ALTER TABLE public.articles
            ALTER COLUMN id SET DEFAULT nextval('public.articles_id_seq');
    END IF;
END
$$;

ALTER SEQUENCE public.articles_id_seq OWNED BY public.articles.id;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'articles_source_id_fkey'
          AND conrelid = 'public.articles'::regclass
    ) THEN
        ALTER TABLE public.articles
            ADD CONSTRAINT articles_source_id_fkey
            FOREIGN KEY (source_id)
            REFERENCES public.sources(id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS public.article_source_map (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL,
    source_id BIGINT NOT NULL REFERENCES public.sources(id) ON DELETE CASCADE,
    confidence NUMERIC DEFAULT 1.0,
    detected_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS article_source_map_article_idx
    ON public.article_source_map (article_id);
CREATE INDEX IF NOT EXISTS article_source_map_source_idx
    ON public.article_source_map (source_id);

CREATE INDEX IF NOT EXISTS idx_articles_metadata
    ON public.articles USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_articles_source_id
    ON public.articles (source_id);

COMMENT ON TABLE public.articles IS 'Primary article storage including metadata and provenance information.';
COMMENT ON COLUMN public.articles.metadata IS 'Arbitrary metadata for the article (JSONB).';
COMMENT ON TABLE public.article_source_map IS 'Provenance mapping between articles and canonical sources.';

COMMIT;
