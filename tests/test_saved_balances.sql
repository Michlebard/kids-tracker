-- Run ONLY in a disposable PostgreSQL database after installing the migration.
-- The transaction rolls back every test operation, including TRUNCATE.
BEGIN;

CREATE FUNCTION pg_temp.assert_balances_match_history()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        WITH names AS (
            SELECT name AS child_name FROM public.children
            UNION SELECT child_name FROM public.points_log
            UNION SELECT child_name FROM public.money_log
            UNION SELECT child_name FROM public.child_balances
        )
        SELECT 1 FROM names
        LEFT JOIN public.child_balances AS balance USING (child_name)
        WHERE names.child_name IS NOT NULL AND (
            COALESCE(balance.points_balance, 0) <>
                (SELECT COALESCE(SUM(points_change), 0) FROM public.points_log
                 WHERE child_name = names.child_name)
            OR COALESCE(balance.money_balance, 0) <>
                (SELECT COALESCE(SUM(amount), 0) FROM public.money_log
                 WHERE child_name = names.child_name)
        )
    ) THEN
        RAISE EXCEPTION 'Stored balances do not match complete history';
    END IF;
END;
$$;

SELECT pg_temp.assert_balances_match_history();

DO $$
DECLARE
    point_id bigint;
    money_id bigint;
    before_rollback numeric;
    after_rollback numeric;
BEGIN
    INSERT INTO public.points_log (child_name, points_change, reason)
        VALUES ('__balance_test_A__', 5, 'test') RETURNING id INTO point_id;
    INSERT INTO public.money_log (child_name, amount, description)
        VALUES ('__balance_test_A__', 3.75, 'test') RETURNING id INTO money_id;
    PERFORM pg_temp.assert_balances_match_history();

    -- Edits apply only the difference, including negative values and zero.
    UPDATE public.points_log SET points_change = -2 WHERE id = point_id;
    UPDATE public.money_log SET amount = -1.25 WHERE id = money_id;
    PERFORM pg_temp.assert_balances_match_history();
    UPDATE public.points_log SET reason = 'text-only edit' WHERE id = point_id;
    UPDATE public.money_log SET description = 'text-only edit' WHERE id = money_id;
    PERFORM pg_temp.assert_balances_match_history();

    -- Moving a record between children cancels the old contribution.
    UPDATE public.points_log SET child_name = '__balance_test_B__' WHERE id = point_id;
    UPDATE public.money_log SET child_name = '__balance_test_B__' WHERE id = money_id;
    PERFORM pg_temp.assert_balances_match_history();

    DELETE FROM public.points_log WHERE id = point_id;
    DELETE FROM public.money_log WHERE id = money_id;
    PERFORM pg_temp.assert_balances_match_history();

    -- A failed operation must roll back its balance change too.
    SELECT points_balance INTO before_rollback FROM public.child_balances
        WHERE child_name = '__balance_test_A__';
    BEGIN
        INSERT INTO public.points_log (child_name, points_change, reason)
            VALUES ('__balance_test_A__', 17, 'rolled back');
        RAISE EXCEPTION USING ERRCODE = 'P0002';
    EXCEPTION WHEN no_data_found THEN
        NULL;
    END;
    SELECT points_balance INTO after_rollback FROM public.child_balances
        WHERE child_name = '__balance_test_A__';
    IF before_rollback IS DISTINCT FROM after_rollback THEN
        RAISE EXCEPTION 'Balance change survived transaction rollback';
    END IF;
    PERFORM pg_temp.assert_balances_match_history();

    IF NOT has_table_privilege('anon', 'public.child_balances', 'SELECT')
       OR has_table_privilege('anon', 'public.child_balances', 'UPDATE')
       OR has_table_privilege('authenticated', 'public.child_balances', 'INSERT')
       OR has_function_privilege('anon', 'public.sync_child_balance()', 'EXECUTE')
    THEN
        RAISE EXCEPTION 'Unexpected public balance permissions';
    END IF;
END;
$$;

TRUNCATE public.points_log;
SELECT pg_temp.assert_balances_match_history();
TRUNCATE public.money_log;
SELECT pg_temp.assert_balances_match_history();

ROLLBACK;
