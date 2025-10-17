BEGIN;

CREATE SEQUENCE IF NOT EXISTS public.articles_id_seq;

ALTER SEQUENCE public.articles_id_seq OWNED BY public.articles.id;

SELECT setval(
    'public.articles_id_seq',
    COALESCE((SELECT MAX(id) FROM public.articles), 0),
    true
);

ALTER TABLE public.articles
    ALTER COLUMN id SET DEFAULT nextval('public.articles_id_seq');

COMMIT;
