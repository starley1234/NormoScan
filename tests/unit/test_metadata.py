def test_validate_metadata():
    from backend.app.services.metadata import validate_metadata
    ok = {"Обозначение":"АБВГ.123456.001","Наименование":"Вал","Литера":"О1","Формат":"А3"}
    errs = validate_metadata(ok)
    assert errs==[]
    bad = {"Наименование":"Вал"}
    errs = validate_metadata(bad)
    assert any(e["field"]=="Обозначение" for e in errs)
    bad2 = {"Обозначение":"АБВГ.123","Наименование":"Вал","Формат":"А99"}
    errs = validate_metadata(bad2)
    assert any(e["field"]=="Формат" for e in errs)

def test_consistency():
    from backend.app.services.metadata import consistency_check
    m1 = {"Обозначение":"АБВГ.001","Наименование":"Вал","Литера":"О1"}
    m2 = {"Обозначение":"АБВГ.001","Наименование":"Вал","Литера":"О1"}
    m3 = {"Обозначение":"АБВГ.002","Наименование":"Вал","Литера":"О1"}
    res = consistency_check([m1,m2])
    assert res["consistent"]==True
    res2 = consistency_check([m1,m3])
    assert res2["consistent"]==False
    assert len(res2["issues"])==1
    assert res2["issues"][0]["field"]=="Обозначение"

def test_extract_all():
    from backend.app.services.metadata import extract_all_technical_metadata
    ocr = "Обозначение АБВГ.123456.001\nНаименование Корпус\nМатериал Сталь 45 ГОСТ 1050-2013\nМасса 1.5\nЛитера О1"
    vlm = {"Обозначение":"АБВГ.123456.001","Наименование":"Корпус"}
    res = extract_all_technical_metadata(ocr, vlm)
    assert res["metadata"]["Обозначение"]=="АБВГ.123456.001"
    assert res["kb"]["designation"]=="АБВГ.123456.001"
