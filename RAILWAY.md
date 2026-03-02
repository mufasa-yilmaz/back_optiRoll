# Railway Deploy Kontrol Listesi

## PORT uyumsuzluğu (8000 vs 8080)

Railway trafiği **kendi atadığı PORT** üzerinden yönlendirir. Uygulama **aynı portta** dinlemelidir.

### ✅ Yapılanlar (repo içi)

- **`main.py`**: `port = int(os.environ.get("PORT", 8000))` — PORT env'den okunuyor.
- **`Procfile`**: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
- **`railway.toml`**: Start command repo'da sabitlendi; **dashboard’daki Start Command’ı geçersiz kılar**.

### Railway Dashboard’da kontrol et

1. **Settings → Start Command**
   - **Boş bırak** (repo’daki `railway.toml` / Procfile kullanılsın)  
   **veya**
   - Şunu yaz: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Asla** sabit port yazma (örn. `--port 8080` veya `--port 8000`).

2. **Root Directory**
   - Servis kök dizini `backend` ise: `main.py`, `Procfile`, `railway.toml` bu dizinde olmalı (şu an öyle).

3. **Redeploy**
   - Değişiklikten sonra yeni deploy al; loglarda `Uvicorn running on http://0.0.0.0:<PORT>` satırındaki port, Railway’in beklediği port olmalı.

### Loglarda göreceğin

Doğru ayarda örnek:

```
Uvicorn running on http://0.0.0.0:8000
Application startup complete.
```

(8000 yerine Railway’in atadığı port görünebilir; önemli olan komutun `$PORT` kullanması.)
