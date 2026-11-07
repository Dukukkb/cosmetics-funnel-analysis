from pathlib import Path
import argparse,os
import psycopg
from psycopg import sql
p=argparse.ArgumentParser();p.add_argument('month',choices=('2019-Oct','2019-Nov'));a=p.parse_args()
dsn=os.environ.get('POSTGRES_DSN')
if not dsn:raise SystemExit('Укажите строку подключения в POSTGRES_DSN')
schema='cosmetics_2019_'+('oct' if a.month.endswith('Oct') else 'nov')
with psycopg.connect(dsn) as db:
 db.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
 db.execute('SELECT setseed(0.42)')
 rows=db.execute('SELECT user_id,user_session,product_id,view_time,cart_time,purchase_time FROM funnel ORDER BY random() LIMIT 2000').fetchall()
 for user,session,product,v,c,purchase in rows:
  events=db.execute('SELECT event_type,ts FROM clean WHERE user_id=%s AND user_session=%s AND product_id=%s ORDER BY ts',(user,session,product)).fetchall()
  views=[t for k,t in events if k=='view'];assert min(views)==v
  carts=[t for k,t in events if k=='cart' and t>v];assert c==min(carts,default=None)
  purchases=[t for k,t in events if k=='purchase' and c is not None and t>c];assert purchase==min(purchases,default=None)
 print('Проверено независимым перебором:',len(rows),'пар сессия-товар')
 print('Одинаковые timestamps между просмотром и добавлением в корзину:',db.execute("SELECT count(*) FROM first_views v WHERE EXISTS (SELECT 1 FROM clean e WHERE e.user_id=v.user_id AND e.user_session=v.user_session AND e.product_id=v.product_id AND e.event_type='cart' AND e.ts=v.view_time)").fetchone()[0])
 print('Одинаковые timestamps между корзиной и покупкой:',db.execute("SELECT count(*) FROM first_carts v WHERE v.cart_time IS NOT NULL AND EXISTS (SELECT 1 FROM clean e WHERE e.user_id=v.user_id AND e.user_session=v.user_session AND e.product_id=v.product_id AND e.event_type='purchase' AND e.ts=v.cart_time)").fetchone()[0])
