# Storage

- `uploads/` — загруженные PDF чертежей
- `gosts/` — папка с сырыми PDF ГОСТов (укажите в UI или .env GOSTS_PATH)
- `gallery/` — изображения эталонов/ошибок Visual RAG
- `pages/` — постраничные PNG (768px) + кропы
- `retrain/` — логи feedback 👎 для дообучения
- `checks/` — архивы отчетов

Пример структуры:
```
storage/
  gosts/ГОСТ 2.104-2006.pdf
  gosts/ГОСТ 2.307-2011.pdf
  gallery/err_001.png
  uploads/abc123_чертеж.pdf
```
