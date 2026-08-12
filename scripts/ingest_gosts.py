#!/usr/bin/env python3
"""
Индексация ГОСТов из сырых PDF: указываете папку, сервис сам ищет и составляет БД.
Пример: python scripts/ingest_gosts.py --gost-dir ./storage/gosts --vector-db memory
"""
import argparse, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.app.services.gost_ingest import ingest_folder
from backend.app.db import SessionLocal, init_db

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--gost-dir", default="./storage/gosts")
    parser.add_argument("--vector-db", default="memory", choices=["memory","qdrant","milvus"])
    args=parser.parse_args()
    os.environ["VECTOR_DB"]=args.vector_db
    init_db()
    db=SessionLocal()
    print(f"Индексация из {args.gost_dir} (vector_db={args.vector_db}) ...")
    res=ingest_folder(args.gost_dir, db)
    print(f"Найдено файлов: {res.get('files_found')}, обработано: {res.get('processed')}")
    for d in res.get("details",[])[:10]:
        print(d)
    db.close()

if __name__=="__main__":
    main()
