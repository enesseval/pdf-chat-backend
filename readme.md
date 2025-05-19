# PDF Chat Backend

Bu proje, PDF dosyaları üzerinden doğal dilde sohbet etmeye olanak tanıyan bir backend uygulamasıdır. Kullanıcılar bir PDF yükledikten sonra bu belgeyle ilgili sorular sorabilir.

## 🚀 Kurulum

### 1. Depoyu klonlayın

```bash
git clone https://github.com/kullaniciadi/pdf-chat-backend.git
cd pdf-chat-backend
```

### 2. Sanal ortam oluşturun ve etkinleştirin

```bash
cd backend
python -m venv myenv
# Windows:
myenv\Scripts\activate
# macOS/Linux:
source myenv/bin/activate
```

### 3. Gerekli paketleri yükleyin

```bash
pip install -r requirements.txt
```

### 🛠️ Kullanım

```bash
python main.py
```

Uygulama başlatıldığında, terminaldeki yönergeleri izleyerek bir PDF yükleyebilir ve doğal dilde sorular sorabilirsiniz.

📦 Gereksinimler

-  Python 3.8+

-  FastAPI

-  PyMuPDF

-  Gemini AI
