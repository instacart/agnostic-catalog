'''
Unit tests for splitting migration files into statements. These don't need a
database, so they run without any credentials:

    $ python3 -m unittest tests.test_run_sql
'''

import unittest

import agnostic.cli


class FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)


def run_sql(sql):
    cursor = FakeCursor()
    agnostic.cli._run_sql(cursor, sql)
    return [statement.strip() for statement in cursor.executed]


class TestRunSql(unittest.TestCase):

    def test_grant_with_leading_line_comments(self):
        ''' GRANT preceded by -- comments is executed. '''
        sql = (
            '-- Grant read access.\n'
            '--\n'
            '-- More detail.\n'
            '\n'
            'GRANT SELECT, INSERT\n'
            '    ON TABLE s.t\n'
            '    TO ROLE r;'
        )
        self.assertEqual(run_sql(sql), [sql])

    def test_grant_with_leading_block_comment(self):
        ''' GRANT preceded by a /* */ comment is executed. '''
        sql = '/* why\n   this grant */\nGRANT SELECT ON TABLE t TO ROLE r;'
        self.assertEqual(run_sql(sql), [sql])

    def test_revoke_with_leading_comment(self):
        ''' REVOKE preceded by a comment is executed. '''
        sql = '-- No longer needed.\nREVOKE INSERT ON TABLE t FROM ROLE r;'
        self.assertEqual(run_sql(sql), [sql])

    def test_commented_grant_after_ddl(self):
        ''' A commented GRANT later in the file is executed. '''
        executed = run_sql(
            'CREATE TABLE t (a INT);\n'
            '\n'
            '-- Let r read it.\n'
            'GRANT SELECT ON TABLE t TO ROLE r;\n'
        )
        self.assertEqual(executed, [
            'CREATE TABLE t (a INT);',
            '-- Let r read it.\nGRANT SELECT ON TABLE t TO ROLE r;',
        ])

    def test_grant_keyword_followed_by_newline(self):
        ''' GRANT/REVOKE followed by a newline or tab is executed. '''
        executed = run_sql('GRANT\n  SELECT ON TABLE t TO ROLE r;\nREVOKE\tINSERT ON TABLE t FROM ROLE r;\n')
        self.assertEqual(len(executed), 2)

    def test_commented_use_warehouse(self):
        ''' USE WAREHOUSE preceded by a comment is executed. '''
        executed = run_sql('-- Big backfill.\nUSE WAREHOUSE my_wh;\nINSERT INTO t VALUES (1);\n')
        self.assertEqual(executed, [
            '-- Big backfill.\nUSE WAREHOUSE my_wh;',
            'INSERT INTO t VALUES (1);',
        ])

    def test_uncommented_grant_and_use_warehouse(self):
        ''' GRANT, REVOKE and USE WAREHOUSE without comments are executed. '''
        statements = [
            'USE WAREHOUSE my_wh;',
            'GRANT SELECT ON TABLE t TO ROLE r;',
            'revoke insert on table t from role r;',
        ]
        self.assertEqual(run_sql('\n'.join(statements) + '\n'), statements)

    def test_commented_out_grant_not_executed(self):
        ''' A GRANT that is inside a comment is not executed. '''
        self.assertEqual(run_sql('-- GRANT SELECT ON TABLE t TO ROLE r;\n'), [])
        self.assertEqual(run_sql('/* GRANT SELECT ON TABLE t TO ROLE r; */\n'), [])

    def test_ddl_and_dml_executed(self):
        ''' DDL and DML statements are executed, with or without comments. '''
        statements = [
            'CREATE TABLE t (a INT);',
            '-- Seed it.\nINSERT INTO t VALUES (1);',
            '/* fix */ UPDATE t SET a = 2;',
            'DELETE FROM t WHERE a = 2;',
            'ALTER TABLE t ADD COLUMN b INT;',
            'DROP TABLE t;',
        ]
        self.assertEqual(run_sql('\n'.join(statements) + '\n'), statements)

    def test_comment_only_sql_not_executed(self):
        ''' Comment-only, whitespace-only and trailing comments are not executed. '''
        self.assertEqual(run_sql(''), [])
        self.assertEqual(run_sql('\n\n  \n'), [])
        self.assertEqual(run_sql('-- nothing here\n'), [])
        self.assertEqual(run_sql('/* nothing\n here */\n'), [])
        self.assertEqual(
            run_sql('CREATE TABLE t (a INT);\n\n-- end of migration\n'),
            ['CREATE TABLE t (a INT);'],
        )


if __name__ == '__main__':
    unittest.main()
