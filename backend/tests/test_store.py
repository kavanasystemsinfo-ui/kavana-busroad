"""Tests del store persistente (JSON en disco) de BusRoad.

El store sobrevive al reinicio del proceso (auto-stop de Fly) y guarda:
- caché de rutas y geocodificación (clave canónica)
- contadores de rate limit (asistente y /ruta)
"""

from app.store import Store


def _nuevo_store(tmp_path):
    return Store(str(tmp_path / "store.json"))


def test_cache_miss_devuelve_none(tmp_path):
    st = _nuevo_store(tmp_path)
    assert st.cache_get("ns", "clave") is None


def test_cache_set_y_get(tmp_path):
    st = _nuevo_store(tmp_path)
    st.cache_set("ns", "clave", [1.0, 2.0])
    assert st.cache_get("ns", "clave") == [1.0, 2.0]


def test_cache_respeta_ttl_vencido(tmp_path):
    st = _nuevo_store(tmp_path)
    st.cache_set("ns", "clave", "valor")
    st._datos["ns"]["clave"]["ts"] = 0  # envejecer la entrada a ojo
    assert st.cache_get("ns", "clave", ttl_seconds=10) is None


def test_persistencia_entre_instancias(tmp_path):
    """Simula un reinicio: una instancia nueva lee lo que guardó la anterior."""
    p = str(tmp_path / "store.json")
    st1 = Store(p)
    st1.cache_set("ns", "clave", {"a": 1})
    st2 = Store(p)
    assert st2.cache_get("ns", "clave") == {"a": 1}


def test_contador_incr_y_get(tmp_path):
    st = _nuevo_store(tmp_path)
    assert st.counter_incr("rl", "1.2.3.4") == 1
    assert st.counter_incr("rl", "1.2.3.4") == 2
    assert st.counter_get("rl", "1.2.3.4") == 2


def test_contador_reinicia_con_ttl_vencido(tmp_path):
    st = _nuevo_store(tmp_path)
    st.counter_incr("rl", "ip", ttl_seconds=10)
    st.counter_incr("rl", "ip", ttl_seconds=10)
    st._datos["rl"]["ip"]["ts"] = 0  # envejecer
    assert st.counter_get("rl", "ip", ttl_seconds=10) == 0


def test_contador_no_reinicia_con_ttl_vivo(tmp_path):
    st = _nuevo_store(tmp_path)
    st.counter_incr("rl", "ip", ttl_seconds=10)
    assert st.counter_get("rl", "ip", ttl_seconds=10) == 1


def test_fichero_corrupto_arranca_vacio_y_sigue_usable(tmp_path):
    p = str(tmp_path / "store.json")
    with open(p, "w") as f:
        f.write("{esto no es json")
    st = Store(p)
    assert st.cache_get("ns", "clave") is None
    st.cache_set("ns", "clave", "v")  # sigue escribiendo pese al fichero corrupto
    assert Store(p).cache_get("ns", "clave") == "v"


def test_clear_borra_todo(tmp_path):
    st = _nuevo_store(tmp_path)
    st.cache_set("ns", "clave", "v")
    st.counter_incr("rl", "ip")
    st.clear()
    assert st.cache_get("ns", "clave") is None
    assert st.counter_get("rl", "ip") == 0