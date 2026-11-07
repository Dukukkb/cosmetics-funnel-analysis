from pathlib import Path
import argparse,csv,json,os
import psycopg
from psycopg import sql
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('month',choices=('2019-Oct','2019-Nov'));p.add_argument('--output',type=Path,default=root/'results');a=p.parse_args()
schema='cosmetics_2019_'+('oct' if a.month.endswith('Oct') else 'nov')
dsn=os.environ.get('POSTGRES_DSN')
if not dsn:raise SystemExit('Укажите строку подключения в POSTGRES_DSN')
out=a.output/a.month;out.mkdir(parents=True,exist_ok=True)
with psycopg.connect(dsn) as db:
 db.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
 query="""WITH purchases AS (SELECT user_id,user_session,product_id,max(ts) purchase_ts FROM clean WHERE event_type='purchase' GROUP BY 1,2,3),
 classified AS (SELECT p.*,f.view_time,f.cart_time,f.purchase_time,
 CASE WHEN f.purchase_time IS NOT NULL THEN 'Полный путь'
 WHEN f.view_time IS NULL THEN 'Нет просмотра товара в сессии'
 WHEN f.view_time>=p.purchase_ts THEN 'Просмотр не раньше покупки'
 WHEN f.cart_time IS NULL THEN 'Нет корзины после просмотра'
 ELSE 'Корзина не раньше покупки' END reason FROM purchases p LEFT JOIN funnel f USING(user_id,user_session,product_id))
 SELECT reason,count(*) pairs FROM classified GROUP BY 1 ORDER BY 2 DESC"""
 def save(q,name):
  c=db.execute(q)
  with (out/name).open('w',newline='',encoding='utf8') as f:
   w=csv.writer(f);w.writerow([x.name for x in c.description]);w.writerows(c.fetchall())
 save(query,'purchase_diagnostics.csv')
 q="""WITH m AS (SELECT category_id,count(*) n,count(*) FILTER(WHERE category_code IS NOT NULL AND category_code<>'') named,
 count(DISTINCT category_code) codes FROM events WHERE category_id IS NOT NULL GROUP BY 1)
 SELECT count(*) category_ids,sum(n) events,sum(n) FILTER(WHERE named>0 AND codes=1) events_unique_mapped_id,
 sum(n) FILTER(WHERE codes>1) events_conflicting_ids,sum(n) FILTER(WHERE named=0) events_without_mapping FROM m"""
 c=db.execute(q);result={k.name:(int(v) if v is not None else None) for k,v in zip(c.description,c.fetchone())}
 (out/'category_mapping.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 save('''SELECT category_id,count(*) viewed_pairs,count(cart_time) carted_pairs,count(purchase_time) purchased_pairs
 FROM funnel GROUP BY 1 ORDER BY 2 DESC''','category_ids.csv')
 print(a.month,result,flush=True)
