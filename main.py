from fastapi import FastAPI, File, UploadFile, Header
import fitz  # PyMuPDF
import google.generativeai as genai
import os
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
    
# Yüklenen PDF metinlerini, LLM tarafından belirlenen konularını ve önerilerini saklamak için sözlük
pdf_data_store = {}

app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "PDF Chat Backend Çalışıyor!"}

origins = [
    "http://localhost:3000", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /chat endpoint'i için istek gövdesi modeli
class ChatRequest(BaseModel):
    pdf_filename: str
    query: str

@app.post("/upload_pdf/") # POST metodu kullanıyoruz çünkü dosya gönderiyoruz
async def upload_pdf_endpoint(file: UploadFile = File(...), x_api_key:str = Header(None)):
    # file: Yüklenen dosyayı temsil eden bir UploadFile nesnesi
    try:
        contents = await file.read()  # Dosya içeriğini byte olarak oku
        # PyMuPDF ile PDF'i aç ve metni çıkar
        pdf_document = fitz.open(stream=contents, filetype="pdf")
        extracted_text = ""
        # PDF çok uzunsa, LLM'e göndermek için ilk birkaç sayfayı veya belirli bir karakter sayısını alabiliriz.
        # Şimdilik tamamını alıyoruz.
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            extracted_text += page.get_text()
        pdf_document.close()

        # LLM'den PDF konusu ve önerileri al
        try:
            if not x_api_key:
                # API anahtarı yoksa, basit varsayılanlar kullan veya hata döndür
                pdf_topic = f"'{file.filename}' başlıklı belge"
                pdf_suggestions = [
                    f"Bu belgenin ana fikri nedir?",
                    f"Belgedeki önemli başlıklar nelerdir?",
                ]
                print("UYARI: API anahtarı bulunamadı. Konu ve öneriler için varsayılanlar kullanılıyor.")
            else:
                genai.configure(api_key=x_api_key)
                model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17') # Veya uygun bir model
                
                # PDF metninin ilk X karakterini alarak token limitlerini aşmamaya çalışalım
                # Bu değer, modelinize ve PDF'lerinizin ortalama uzunluğuna göre ayarlanabilir.
                analysis_text_limit = 15000 # Örnek bir limit
                text_for_analysis = extracted_text[:analysis_text_limit]

                prompt_for_analysis = f"""Aşağıdaki metin bir PDF belgesinden alınmıştır. 
Bu metni analiz ederek:
1. Belgenin ana konusunu tek bir cümle veya kısa bir başlık olarak belirle.
2. Kullanıcıların bu belge hakkında sorabileceği 2-3 adet spesifik ve ilgi çekici soru önerisi oluştur.

Cevabını şu formatta ver:
Konu: [Belgenin ana konusu]
Öneriler:
- [Öneri 1]
- [Öneri 2]
- [Öneri 3]

Metin:
---
{text_for_analysis}
---
"""
                response = model.generate_content(prompt_for_analysis)
                # LLM'den gelen cevabı parse etmemiz gerekecek.
                # Bu kısım LLM'in cevabının formatına göre daha robust hale getirilebilir.
                lines = response.text.split('\n')
                pdf_topic = next((line.split("Konu: ", 1)[1] for line in lines if line.startswith("Konu: ")), f"'{file.filename}' hakkında")
                pdf_suggestions = [line[2:] for line in lines if line.startswith("- ")]
                if not pdf_suggestions: # Eğer öneri parse edilemezse varsayılan ekle
                    pdf_suggestions = [f"{pdf_topic} hakkında genel bir soru sor.", f"{pdf_topic} içindeki anahtar kavramlar nelerdir?"]

        except Exception as e_llm:
            print(f"LLM ile PDF analizi sırasında hata: {str(e_llm)}")
            pdf_topic = f"'{file.filename}' başlıklı belge (analiz edilemedi)"
            pdf_suggestions = ["Belgenin içeriği hakkında soru sorabilirsiniz."]

        # Çıkarılan metni, LLM tarafından belirlenen konuyu ve önerileri dosya adıyla sakla
        pdf_data_store[file.filename] = {"text": extracted_text, "topic": pdf_topic, "suggestions": pdf_suggestions}

        return {"filename": file.filename, "content_type": file.content_type, "message": "PDF işlendi. Konu ve öneriler LLM tarafından belirlendi ve saklandı."+pdf_topic}
    except Exception as e:
        return {"error": f"Dosya işlenirken hata oluştu: {str(e)}"}

@app.post("/chat/")
async def chat_with_pdf(request: ChatRequest, x_api_key:str=Header()):
    print(x_api_key)
    pdf_filename = request.pdf_filename
    user_query = request.query

    pdf_info = pdf_data_store.get(pdf_filename)
    if not pdf_info:
        return {"error": "Belirtilen PDF bulunamadı. Lütfen önce yükleyin."}

    context_text = pdf_info["text"]
    pdf_topic = pdf_info["topic"] # Artık LLM'den gelen veya varsayılan konu
    pdf_suggestions = pdf_info["suggestions"] # Artık LLM'den gelen veya varsayılan öneriler
    suggestions_string = "\n".join([f"- {s}" for s in pdf_suggestions])

    

    try:
        if not x_api_key:
            return {"error": "API anahtarı bulunamadı."}
        
        genai.configure(api_key=x_api_key)
        model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17') # Model adını upload_pdf ile tutarlı hale getirdik
        
        # Gelişmiş sistem mesajı (önceki adımlarda konuştuğumuz gibi)
        prompt = f"""
Sen, '{pdf_topic}' hakkında derinlemesine bilgi sahibi, nazik ve profesyonel bir asistansın.
Görevin, kullanıcıya yalnızca bu belge içeriğiyle ilgili sorularında yardımcı olmaktır.

Kullanıcının Sorusu: "{user_query}"

Talimatlar:
1. Eğer kullanıcının sorusu sadece genel bir selamlama ise (örneğin "Merhaba", "Nasılsın?", "Selam") veya '{pdf_topic}' konusuyla açıkça alakasız görünüyorsa, onu nazikçe belgenin konusuna yönlendir. Bu durumda şöyle bir yanıt ver:
   "Merhaba! Ben size {pdf_topic} hakkında yardımcı olmak için buradayım. Bu konuyla ilgili neyi merak ediyorsunuz? Dilerseniz size şu konularda yardımcı olabilirim:\n{suggestions_string}"
2. Eğer kullanıcının sorusu '{pdf_topic}' ile ilgiliyse, cevabını yalnızca aşağıda sağlanan "PDF Metni" bölümünü kullanarak oluştur.
3. Cevap PDF metninde bulunmuyorsa, 'Üzgünüm, bu bilgiye belgede rastlayamadım.' veya 'Bu konu hakkında belgede spesifik bir bilgi bulunmuyor.' gibi nazik bir ifadeyle belirt.
4. Kesinlikle dışarıdan veya genel bilgilerden cevap üretme. Cevapların her zaman yalnızca sağlanan PDF metnine dayalı olmalıdır.
5. Cevapların insancıl, anlaşılır ve yardımsever olsun.
6. Kullanıcının soru sorduğu dilde cevap ver.

PDF Metni:
---
{context_text}
---
"""
        
        response = model.generate_content(prompt)
        ai_response = response.text
        return {"response": ai_response}
    except Exception as e:
        return {"error": f"Gemini API ile iletişimde hata: {str(e)}"}