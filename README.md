# Анализ воронки интернет-магазина косметики

Анализ последовательности просмотра, добавления в корзину и покупки одного товара в пределах сессии. Данные за октябрь и ноябрь 2019 года обработаны с помощью PostgreSQL и Python.

## Результаты

| Переход | Октябрь | Ноябрь |
|---|---:|---:|
| Просмотр и добавление в корзину | 17,60% | 12,97% |
| Добавление в корзину и покупка | 9,83% | 15,03% |

Конверсии рассчитаны по сессиям. Правила расчёта и результаты проверки данных описаны в отчёте.

- [Ноутбук](анализ.ipynb)
- [Отчёт](docs/отчёт.md)
- [Дашборд в DataLens](https://datalens.yandex/hs3znlxv4pn40?_share_link=public)

## Запуск

Нужны Python 3.13, PostgreSQL и файлы `2019-Oct.csv` и `2019-Nov.csv` из [датасета Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop). Исходные данные помещаются в папку `data/` и не входят в Git.

Для локального запуска PostgreSQL через Docker:

```bash
docker run -d --name analytics-postgres -e POSTGRES_PASSWORD=analytics_local \
  -e POSTGRES_DB=analytics -p 127.0.0.1:55432:5432 postgres:16-alpine
```

Из папки проекта:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export POSTGRES_DSN='postgresql://postgres:analytics_local@127.0.0.1:55432/analytics'
python src/prepare_data.py
python src/analyze.py 2019-Oct
python src/analyze.py 2019-Nov
python src/diagnose.py 2019-Oct
python src/diagnose.py 2019-Nov
python src/verify.py 2019-Oct
python src/verify.py 2019-Nov
python src/verify_full.py
python src/present.py
```

Для Windows активация окружения: `.venv\Scripts\activate`. Для существующего сервера укажите его адрес в `POSTGRES_DSN`.

`prepare_data.py` проверяет контрольные суммы CSV и при необходимости извлекает их из `data/2019-Oct.zip` и `data/2019-Nov.zip`. При повторной загрузке месяца добавьте к `src/analyze.py` флаг `--replace`. Дашборд использует сохранённую агрегированную таблицу.

## Структура

- `src/` содержит скрипты анализа и проверок.
- `results/` содержит таблицы результатов и график.
- `data/` предназначена для исходных данных.

Источник: [eCommerce Events History in Cosmetics Shop](https://www.kaggle.com/mkechinov/ecommerce-events-history-in-cosmetics-Shop), Open CDP и [REES46 Marketing Platform](https://rees46.com/).
