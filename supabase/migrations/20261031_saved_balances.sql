-- Run the complete script once in Supabase SQL Editor as the database owner.
-- No history is deleted. Re-running rebuilds balances from the complete logs.
BEGIN;

-- Block writes while installing triggers and taking the initial snapshot.
-- Readers may continue, and queued writers resume after COMMIT.
LOCK TABLE public.children, public.points_log, public.money_log
    IN SHARE ROW EXCLUSIVE MODE;

CREATE TABLE IF NOT EXISTS public.child_balances (
    child_name text PRIMARY KEY,
    points_balance bigint NOT NULL DEFAULT 0,
    money_balance numeric NOT NULL DEFAULT 0
);
LOCK TABLE public.child_balances IN SHARE ROW EXCLUSIVE MODE;

-- Reads follow the existing public dashboard model. Only triggers/the owner
-- may change totals; API clients must continue writing to the log tables.
ALTER TABLE public.child_balances ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS read_child_balances ON public.child_balances;
CREATE POLICY read_child_balances ON public.child_balances
    FOR SELECT TO anon, authenticated USING (true);
REVOKE ALL ON public.child_balances FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON public.child_balances TO anon, authenticated, service_role;

-- SECURITY DEFINER is needed because clients cannot write the balance table.
-- No dynamic SQL; objects are qualified and the search path is fixed.
CREATE OR REPLACE FUNCTION public.sync_child_balance()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    old_name text;
    new_name text;
    old_points bigint := 0;
    new_points bigint := 0;
    old_money numeric := 0;
    new_money numeric := 0;
BEGIN
    IF TG_OP = 'TRUNCATE' THEN
        IF TG_TABLE_NAME = 'points_log' THEN
            UPDATE public.child_balances SET points_balance = 0;
        ELSE
            UPDATE public.child_balances SET money_balance = 0;
        END IF;
        RETURN NULL;
    END IF;

    IF TG_OP <> 'INSERT' THEN
        old_name := OLD.child_name;
        IF TG_TABLE_NAME = 'points_log' THEN
            old_points := COALESCE(OLD.points_change, 0);
        ELSE
            old_money := COALESCE(OLD.amount, 0);
        END IF;
    END IF;
    IF TG_OP <> 'DELETE' THEN
        new_name := NEW.child_name;
        IF TG_TABLE_NAME = 'points_log' THEN
            new_points := COALESCE(NEW.points_change, 0);
        ELSE
            new_money := COALESCE(NEW.amount, 0);
        END IF;
    END IF;

    IF TG_OP = 'UPDATE' AND old_name IS NOT DISTINCT FROM new_name THEN
        IF new_name IS NOT NULL THEN
            INSERT INTO public.child_balances AS balances
                (child_name, points_balance, money_balance)
            VALUES (new_name, new_points - old_points, new_money - old_money)
            ON CONFLICT (child_name) DO UPDATE SET
                points_balance = balances.points_balance + EXCLUDED.points_balance,
                money_balance = balances.money_balance + EXCLUDED.money_balance;
        END IF;
    ELSE
        IF old_name IS NOT NULL THEN
            INSERT INTO public.child_balances AS balances
                (child_name, points_balance, money_balance)
            VALUES (old_name, -old_points, -old_money)
            ON CONFLICT (child_name) DO UPDATE SET
                points_balance = balances.points_balance + EXCLUDED.points_balance,
                money_balance = balances.money_balance + EXCLUDED.money_balance;
        END IF;
        IF new_name IS NOT NULL THEN
            INSERT INTO public.child_balances AS balances
                (child_name, points_balance, money_balance)
            VALUES (new_name, new_points, new_money)
            ON CONFLICT (child_name) DO UPDATE SET
                points_balance = balances.points_balance + EXCLUDED.points_balance,
                money_balance = balances.money_balance + EXCLUDED.money_balance;
        END IF;
    END IF;
    RETURN NULL;
END;
$$;
REVOKE ALL ON FUNCTION public.sync_child_balance()
    FROM PUBLIC, anon, authenticated, service_role;

DROP TRIGGER IF EXISTS sync_points_balance ON public.points_log;
CREATE TRIGGER sync_points_balance
    AFTER INSERT OR UPDATE OR DELETE ON public.points_log
    FOR EACH ROW EXECUTE FUNCTION public.sync_child_balance();
DROP TRIGGER IF EXISTS sync_money_balance ON public.money_log;
CREATE TRIGGER sync_money_balance
    AFTER INSERT OR UPDATE OR DELETE ON public.money_log
    FOR EACH ROW EXECUTE FUNCTION public.sync_child_balance();
DROP TRIGGER IF EXISTS truncate_points_balance ON public.points_log;
CREATE TRIGGER truncate_points_balance AFTER TRUNCATE ON public.points_log
    FOR EACH STATEMENT EXECUTE FUNCTION public.sync_child_balance();
DROP TRIGGER IF EXISTS truncate_money_balance ON public.money_log;
CREATE TRIGGER truncate_money_balance AFTER TRUNCATE ON public.money_log
    FOR EACH STATEMENT EXECUTE FUNCTION public.sync_child_balance();

CREATE INDEX IF NOT EXISTS points_log_recent_idx
    ON public.points_log (date_added DESC, id DESC);
CREATE INDEX IF NOT EXISTS money_log_recent_idx
    ON public.money_log (date_added DESC, id DESC);

-- Include children without transactions as well as historical child names.
-- Calculate points and money independently to avoid multiplying joined rows.
INSERT INTO public.child_balances AS balances
    (child_name, points_balance, money_balance)
SELECT child_name, SUM(points)::bigint, SUM(money)
FROM (
    SELECT name AS child_name, 0::bigint AS points, 0::numeric AS money
        FROM public.children
    UNION ALL
    SELECT child_name, COALESCE(points_change, 0)::bigint, 0::numeric
        FROM public.points_log
    UNION ALL
    SELECT child_name, 0::bigint, COALESCE(amount, 0)::numeric
        FROM public.money_log
) AS history
WHERE child_name IS NOT NULL
GROUP BY child_name
ON CONFLICT (child_name) DO UPDATE SET
    points_balance = EXCLUDED.points_balance,
    money_balance = EXCLUDED.money_balance;

-- Reset obsolete names too if the script is re-run after manual cleanup.
UPDATE public.child_balances AS balances
SET points_balance = 0, money_balance = 0
WHERE NOT EXISTS (SELECT 1 FROM public.children WHERE name = balances.child_name)
  AND NOT EXISTS (SELECT 1 FROM public.points_log WHERE child_name = balances.child_name)
  AND NOT EXISTS (SELECT 1 FROM public.money_log WHERE child_name = balances.child_name);

NOTIFY pgrst, 'reload schema';
COMMIT;

SELECT child_name, points_balance, money_balance
FROM public.child_balances ORDER BY child_name;
