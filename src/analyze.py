"""Анализ воронки магазина косметики в PostgreSQL."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import psycopg
from psycopg import sql

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('month',choices=('2019-Oct','2019-Nov'))
p.add_argument('--replace',action='store_true',help='Пересоздать схему выбранного месяца')
p.add_argument('--output',type=Path,default=root/'results')
a=p.parse_args(); month=a.month
source=root/'data'/f'{month}.csv'; out=a.output/month; out.mkdir(parents=True,exist_ok=True)
dsn=os.environ.get('POSTGRES_DSN')
if not dsn: raise SystemExit('Укажите строку подключения в POSTGRES_DSN')
schema='cosmetics_2019_'+('oct' if month.endswith('Oct') else 'nov')
with psycopg.connect(dsn) as db:
 exists=db.execute('SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname=%s)',(schema,)).fetchone()[0]
 if exists and not a.replace: raise SystemExit(f'Схема {schema} уже существует. Для пересоздания добавьте --replace.')
 if exists: db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
 db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
 db.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
 db.execute("SET timezone='UTC'")
 db.execute('''CREATE TABLE events(ts timestamptz, event_type text, product_id text,category_id text,
    category_code text,brand text,price text,user_id text,user_session text)''')
 print('Загружаем события:',month,flush=True)
 with db.cursor().copy('COPY events FROM STDIN WITH (FORMAT CSV, HEADER TRUE)') as copy:
  with source.open('rb') as f:
   while chunk:=f.read(1024*1024):copy.write(chunk)
 db.execute('CREATE INDEX events_session_idx ON events(user_id,user_session,product_id,event_type,ts)')
 db.execute('ANALYZE events')
 def one(q):
  c=db.execute(q);return dict(zip([x.name for x in c.description],c.fetchone()))
 def save(q,name):
  c=db.execute(q)
  with (out/name).open('w',newline='',encoding='utf8') as f:
   w=csv.writer(f);w.writerow([x.name for x in c.description])
   while batch:=c.fetchmany(10000):w.writerows(batch)
 quality=one("""SELECT count(*) events, count(distinct user_id) users, count(distinct user_session) sessions,
 count(*) FILTER (WHERE user_id IS NULL OR user_id='') missing_user,
 count(*) FILTER (WHERE user_session IS NULL OR user_session='') missing_session,
 count(*) FILTER (WHERE product_id IS NULL OR product_id='') missing_product,
 count(*) FILTER (WHERE ts IS NULL) missing_time,
 count(*) FILTER (WHERE category_code IS NULL OR category_code='') missing_category_code,
 min(ts)::text min_time, max(ts)::text max_time FROM events""")
 print('Проверяем качество данных...',flush=True)
 quality['duplicate_rows']=int(db.execute('SELECT coalesce(sum(n-1),0) FROM (SELECT count(*) n FROM events GROUP BY ts,event_type,product_id,category_id,category_code,brand,price,user_id,user_session HAVING count(*)>1) x').fetchone()[0])
 quality['sessions_multiple_users']=db.execute('SELECT count(*) FROM (SELECT user_session FROM events WHERE user_session IS NOT NULL AND user_id IS NOT NULL GROUP BY user_session HAVING count(DISTINCT user_id)>1) x').fetchone()[0]
 with source.open('rb') as f: quality['sha256']=hashlib.file_digest(f,'sha256').hexdigest()
 save('SELECT event_type,count(*) AS events FROM events GROUP BY event_type ORDER BY events DESC','event_types.csv')
 start,end={'2019-Oct':('2019-10-02','2019-10-31'),'2019-Nov':('2019-11-02','2019-11-30')}[month]
 db.execute('''CREATE TABLE eligible AS SELECT user_id,user_session FROM events
 WHERE user_id IS NOT NULL AND user_session IS NOT NULL AND ts IS NOT NULL
 GROUP BY user_id,user_session HAVING min(ts)>=%s::timestamptz AND min(ts)<%s::timestamptz''',(start,end))
 db.execute('CREATE UNIQUE INDEX ON eligible(user_id,user_session)');db.execute('ANALYZE eligible')
 db.execute('''CREATE TABLE clean AS SELECT e.* FROM events e JOIN eligible s USING(user_id,user_session)
 WHERE e.ts IS NOT NULL AND e.product_id IS NOT NULL''')
 db.execute('CREATE INDEX clean_lookup_idx ON clean(user_id,user_session,product_id,event_type,ts)')
 db.execute('ANALYZE clean')
 print('Строим воронку...',flush=True)
 db.execute('''CREATE TABLE first_views AS SELECT user_id,user_session,product_id,min(ts) view_time,
 (array_agg(category_code ORDER BY ts) FILTER (WHERE category_code IS NOT NULL AND category_code<>''))[1] category_code,
 (array_agg(category_id ORDER BY ts) FILTER (WHERE category_id IS NOT NULL))[1] category_id
 FROM clean WHERE event_type='view' GROUP BY user_id,user_session,product_id''')
 db.execute('CREATE UNIQUE INDEX ON first_views(user_id,user_session,product_id)');db.execute('ANALYZE first_views')
 db.execute('''CREATE TABLE first_carts AS SELECT v.*,min(e.ts) cart_time FROM first_views v
 LEFT JOIN clean e ON v.user_id=e.user_id AND v.user_session=e.user_session AND v.product_id=e.product_id
 AND e.event_type='cart' AND e.ts>v.view_time
 GROUP BY v.user_id,v.user_session,v.product_id,v.view_time,v.category_code,v.category_id''')
 db.execute('CREATE UNIQUE INDEX ON first_carts(user_id,user_session,product_id)');db.execute('ANALYZE first_carts')
 db.execute('''CREATE TABLE funnel AS SELECT c.*,min(e.ts) purchase_time FROM first_carts c
 LEFT JOIN clean e ON c.user_id=e.user_id AND c.user_session=e.user_session AND c.product_id=e.product_id
 AND e.event_type='purchase' AND e.ts>c.cart_time
 GROUP BY c.user_id,c.user_session,c.product_id,c.view_time,c.category_code,c.category_id,c.cart_time''')
 db.execute('CREATE UNIQUE INDEX ON funnel(user_id,user_session,product_id)');db.execute('ANALYZE funnel')
 quality.update(one("SELECT count(*) session_product_views, count(cart_time) session_product_carts, count(purchase_time) session_product_purchases, count(*) FILTER (WHERE category_code IS NULL) viewed_pairs_missing_category FROM funnel"))
 quality.update(one('''SELECT count(DISTINCT (user_id,user_session)) eligible_sessions,
 count(DISTINCT (user_id,user_session)) FILTER (WHERE event_type='view') sessions_with_view,
 count(DISTINCT (user_id,user_session)) FILTER (WHERE event_type='cart') sessions_with_cart,
 count(DISTINCT (user_id,user_session)) FILTER (WHERE event_type='purchase') sessions_with_purchase FROM clean'''))
 quality.update(one('''SELECT count(*) purchasing_pairs,count(*) FILTER (WHERE f.purchase_time IS NULL) purchasing_pairs_not_in_funnel FROM
 (SELECT DISTINCT user_id,user_session,product_id FROM clean WHERE event_type='purchase') p
 LEFT JOIN funnel f USING(user_id,user_session,product_id)'''))
 quality.update(one('''SELECT count(*) purchasing_sessions,count(*) FILTER (WHERE f.user_session IS NULL) purchasing_sessions_not_in_funnel FROM
 (SELECT DISTINCT user_id,user_session FROM clean WHERE event_type='purchase') p LEFT JOIN
 (SELECT DISTINCT user_id,user_session FROM funnel WHERE purchase_time IS NOT NULL) f USING(user_id,user_session)'''))
 quality.update(one('''SELECT count(DISTINCT (user_id,user_session)) sessions_in_funnel_view,
 count(DISTINCT (user_id,user_session)) FILTER (WHERE cart_time IS NOT NULL) sessions_in_funnel_cart,
 count(DISTINCT (user_id,user_session)) FILTER (WHERE purchase_time IS NOT NULL) sessions_in_funnel_purchase FROM funnel'''))
 quality.update(one('''SELECT count(*) pairs,count(*) FILTER (WHERE p.last_purchase>v.view_time) pairs_with_prior_view,
 count(*) FILTER (WHERE c.cart_time IS NOT NULL AND p.last_purchase>c.cart_time) pairs_with_prior_cart FROM
 (SELECT user_id,user_session,product_id,max(ts) last_purchase FROM clean WHERE event_type='purchase' GROUP BY 1,2,3) p
 LEFT JOIN first_views v USING(user_id,user_session,product_id) LEFT JOIN first_carts c USING(user_id,user_session,product_id)'''))
 save('''SELECT coalesce(category_code,'Не указана') category,count(*) viewed,count(cart_time) carted,
 count(purchase_time) purchased,round(100.0*count(cart_time)/count(*),3) view_to_cart_pct,
 round(100.0*count(purchase_time)/nullif(count(cart_time),0),3) cart_to_purchase_pct
 FROM funnel GROUP BY 1 ORDER BY viewed DESC''','categories.csv')
 save("""SELECT to_char(view_time AT TIME ZONE 'UTC','YYYY-MM-DD') event_date,count(*) viewed,count(cart_time) carted,
 count(purchase_time) purchased FROM funnel GROUP BY 1 ORDER BY 1""",'daily.csv')
 (out/'quality.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
 print(json.dumps(quality,ensure_ascii=False,indent=2,default=str),flush=True)
