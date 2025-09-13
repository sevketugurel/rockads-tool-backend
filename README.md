# FastAPI Clean Architecture Backend

React projenizle bağlantı kurmak için clean architecture ile geliştirilmiş FastAPI backend projesi.

## Proje Yapısı

```
backend/
├── domain/                 # Domain katmanı (entities, repositories)
│   ├── entities/          # İş varlıkları
│   └── repositories/      # Repository interface'leri
├── infrastructure/        # Infrastructure katmanı
│   ├── database/         # Veritabanı implementasyonları
│   └── external/         # Harici servisler
├── application/          # Application katmanı
│   ├── use_cases/       # İş kuralları
│   └── services/        # Servisler
├── presentation/         # Presentation katmanı
│   ├── api/            # API route'ları
│   └── middleware/     # Middleware'ler
├── core/                # Core yapılandırma
│   ├── config/         # Uygulama ayarları
│   └── exceptions/     # Özel exception'lar
└── main.py             # FastAPI ana dosyası
```

## Kurulum

1. **Sanal ortam oluşturun:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # macOS/Linux
# veya
venv\Scripts\activate     # Windows
```

2. **Bağımlılıkları yükleyin:**
```bash
pip install -r requirements.txt
```

3. **Uygulamayı başlatın:**
```bash
python main.py
# veya
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Users
- `GET /api/users/` - Tüm kullanıcıları listele
- `POST /api/users/` - Yeni kullanıcı oluştur
- `GET /api/users/{user_id}` - Kullanıcı detayı
- `GET /api/users/email/{email}` - Email ile kullanıcı ara
- `PUT /api/users/{user_id}` - Kullanıcı güncelle
- `DELETE /api/users/{user_id}` - Kullanıcı sil

### Items
- `GET /api/items/` - Tüm öğeleri listele
- `POST /api/items/` - Yeni öğe oluştur
- `GET /api/items/{item_id}` - Öğe detayı
- `GET /api/items/user/{user_id}` - Kullanıcının öğelerini listele
- `PUT /api/items/{item_id}` - Öğe güncelle
- `DELETE /api/items/{item_id}` - Öğe sil

### Genel
- `GET /` - Ana sayfa
- `GET /health` - Sağlık kontrolü

## React Entegrasyonu

Backend otomatik olarak aşağıdaki origin'lere CORS desteği sağlar:
- `http://localhost:3000` (Create React App)
- `http://localhost:5173` (Vite)
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

## Örnek Kullanım

### User oluşturma:
```javascript
const response = await fetch('http://localhost:8000/api/users/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    username: 'john_doe',
    email: 'john@example.com',
    full_name: 'John Doe'
  })
});
```

### Item oluşturma:
```javascript
const response = await fetch('http://localhost:8000/api/items/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    name: 'Sample Item',
    description: 'This is a sample item',
    price: 29.99,
    user_id: 1
  })
});
```

## Geliştirme

API dokümantasyonu için `http://localhost:8000/docs` adresini ziyaret edin.

Backend başarıyla çalıştığında React projenizden API çağrıları yapabilirsiniz.