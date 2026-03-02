# Railway Deploy Kontrol Listesi

## PORT uyumsuzluğu (8000 vs 8080)

Railway trafiği **kendi atadığı PORT** üzerinden yönlendirir. Uygulama **aynı portta** dinlemelidir.

### ✅ Yapılanlar (repo içi)

- **`main.py`**: `port = int(os.environ.get("PORT", 8000))` — PORT env'den okunuyor.
- **`Procfile`**: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
- **`railway.toml`**: Start command repo'da sabitlendi; **dashboard'daki Start Command'ı geçersiz kılar**.

### Railway Dashboard'da kontrol et

1. **Settings → Start Command**
   - **Boş bırak** (repo'daki `railway.toml` / Procfile kullanılsın)  
   **veya**
   - Şunu yaz: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Asla** sabit port yazma (örn. `--port 8080` veya `--port 8000`).

2. **Root Directory**
   - Servis kök dizini `backend` ise: `main.py`, `Procfile`, `railway.toml` bu dizinde olmalı (şu an öyle).

3. **Redeploy**
   - Değişiklikten sonra yeni deploy al; loglarda `Uvicorn running on http://0.0.0.0:<PORT>` satırındaki port, Railway'in beklediği port olmalı.

### Loglarda göreceğin

Doğru ayarda örnek:

```
Uvicorn running on http://0.0.0.0:8000
Application startup complete.
```

(8000 yerine Railway'in atadığı port görünebilir; önemli olan komutun `$PORT` kullanması.)

---

## Supabase: "Invalid API key" hatası

Backend şu ortam değişkenlerini kullanır:

| Railway'deki adı      | Açıklama |
|-----------------------|----------|
| `SUPABASE_URL`        | Proje URL'in (örn. `https://xxxxx.supabase.co`) |
| `SUPABASE_SERVICE_KEY`| **Service role** secret key (anon key değil) |

### Hata alıyorsan kontrol et

1. **Doğru anahtar:** Supabase Dashboard → **Project Settings** → **API** bölümünde:
   - **Project URL** → `SUPABASE_URL` olarak kopyala.
   - **Project API keys** içinden **`service_role`** (secret) → `SUPABASE_SERVICE_KEY` olarak kopyala.
   - **`anon` (public) key'i kullanma**; backend için mutlaka `service_role` gerekir.

2. **Eksik/yanlış kopya:** Anahtar `eyJ...` ile başlayan uzun bir metin olmalı. Başında/sonunda boşluk veya satır sonu kalmamalı.

3. **Railway'de:** Servis → **Variables** → `SUPABASE_URL` ve `SUPABASE_SERVICE_KEY` tanımlı mı, değerler doğru mu kontrol et. Değiştirdiysen **Redeploy** yap.
