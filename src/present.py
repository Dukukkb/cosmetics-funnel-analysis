from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).resolve().parents[1]; result=p/'results'
rows=[]
for month,label in [('2019-Oct','Октябрь 2019'),('2019-Nov','Ноябрь 2019')]:
 q=json.loads((result/month/'quality.json').read_text()); s=[q['sessions_in_funnel_view'],q['sessions_in_funnel_cart'],q['sessions_in_funnel_purchase']]
 for i,(stage,n) in enumerate(zip(['1 Просмотр','2 Корзина после просмотра','3 Покупка после корзины'],s)):
  rows.append({'month':label,'stage':stage,'stage_order':i+1,'sessions':n,'conversion_pct':100 if i==0 else 100*n/s[i-1]})
df=pd.DataFrame(rows); df.to_csv(result/'dashboard_funnel.csv',index=False)
fig,ax=plt.subplots(figsize=(9,4.8)); x=range(3); w=.36
for offset,label in [(-w/2,'Октябрь 2019'),(w/2,'Ноябрь 2019')]:
 d=df[df.month==label]; bars=ax.bar([i+offset for i in x],d.sessions,width=w,label=label)
 for bar in bars: ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+14000,f'{bar.get_height():,.0f}'.replace(',',' '),ha='center',fontsize=8)
ax.set_xticks(list(x),['Просмотр','Корзина','Покупка']); ax.set_ylim(0,950000); ax.set_ylabel('Число сессий'); ax.set_title('Путь одного товара в пределах сессии',loc='left'); ax.legend(); ax.spines[['top','right']].set_visible(False); fig.tight_layout(); fig.savefig(result/'сравнение.png',dpi=160); plt.close(fig)
print(df.to_string(index=False))
