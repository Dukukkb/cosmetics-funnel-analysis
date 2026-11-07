import os
import argparse
import psycopg
from psycopg import sql

dsn=os.environ.get('POSTGRES_DSN')
if not dsn:raise SystemExit('Укажите строку подключения в POSTGRES_DSN')
p=argparse.ArgumentParser()
p.add_argument('month',nargs='?',choices=('2019-Oct','2019-Nov'))
a=p.parse_args()
for m in ((a.month,) if a.month else ('2019-Oct','2019-Nov')):
 c=psycopg.connect(dsn)
 schema='cosmetics_2019_'+('oct' if m.endswith('Oct') else 'nov')
 c.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
 r=c.execute('''WITH times AS (
 SELECT user_id,user_session,product_id,ts,
 bool_or(event_type='view') v, bool_or(event_type='cart') c, bool_or(event_type='purchase') p
 FROM clean WHERE event_type in ('view','cart','purchase') GROUP BY 1,2,3,4),
 first_state AS (SELECT *, coalesce(max(CASE WHEN v THEN 1 ELSE 0 END) OVER (PARTITION BY user_id,user_session,product_id ORDER BY ts ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) prev_view FROM times),
 second_state AS (SELECT *, coalesce(max(CASE WHEN c AND prev_view=1 THEN 1 ELSE 0 END) OVER (PARTITION BY user_id,user_session,product_id ORDER BY ts ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) prev_cart FROM first_state),
 sessions AS (SELECT user_id,user_session,bool_or(v) v, bool_or(c AND prev_view=1) c,bool_or(p AND prev_cart=1) p FROM second_state GROUP BY 1,2)
 SELECT count(*) FILTER(WHERE v),count(*) FILTER(WHERE c),count(*) FILTER(WHERE p) FROM sessions''').fetchone()
 target=c.execute('''SELECT count(DISTINCT (user_id,user_session)), count(DISTINCT (user_id,user_session)) FILTER(WHERE cart_time IS NOT NULL), count(DISTINCT (user_id,user_session)) FILTER(WHERE purchase_time IS NOT NULL) FROM funnel''').fetchone()
 print(m,'альтернативный расчёт:',r,'основной расчёт:',target,'совпадают:',r==target,flush=True)
 assert r==target
 c.close()
