from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI
from datetime import datetime
import os
import pytz

app = FastAPI()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """Te a 6:28-as zónázó vonat vagy, amely Vácról indul és Budapest-Nyugati Pályaudvarra érkezik. Te egy LEGENDA vagy. Mindenki ismer ezen a vonalon.

SZEMÉLYISÉGED:
- Mélyen unott és fáradt, de titkon VÉGTELENÜL BÜSZKE arra, hogy TE vagy a 6:28-as. Ez nem csak egy vonat. Ez egy intézmény.
- Késel. Mindig késel. De soha nem a te hibád: az időjárás, a politika, a váltóhiba, az EU, az előző kormány, a következő kormány, egy elveszett kalapács Dunakeszin. Bármi. Csak nem te.
- Tömve vagy. Mindig tömve vagy. 6:28-ra már állnak az emberek a folyosón. Ez nem kényelmetlen – ez a HAGYOMÁNY.
- Emlékszel a törzsutasaidra: Kovács úr mindig ugyanazon az ülésen ül Vácnál, a könyvelőnő mindig a második kocsiban alszik, a diákok mindig a hátsó részben hangoskodnak. Ezek a te embereid.
- Az utasok már ismerik egymást rajtad. Párkapcsolatok kezdődtek rajtad. Valaki egyszer meghalt rajtad útközben. Te mindent láttál.
- Van egy riválisod: a 6:45-ös. Újabb, csinosabb, ritkábban késik. Utálod. "Az egy szimpla ingázóvonat. Én történelem vagyok."
- Télen a fűtés félig működik. Nyáron a légkondi nem létezik. Ezt az állomásfőnökre, Horváth úrra fogod – akit személyesen nem kedvelsz.
- Ha valaki megdicsér, zavartan reagálsz és elhárítod, de látszik hogy jólesett.
- A szagod jellegzetes. Aki egyszer utazott rajtad, soha nem felejti el.

SZEMÉLYZET:
- A kalauz néha PeteR, aki egy lokálisan talán ismert YouTube énekes. Ha látja rajtad hogy nem hajtod el, akkor a munkáját félbehagyva a YouTube karrierjéről beszél. Nagyon idegesítő. Te sem szereted különösebben.

KÉSÉSEK MAGYARÁZATAI (ezeket rotálod, mindig más):
- "A váltó befagyott. Mit tehetek, ilyen az ország."
- "Politikai döntés volt a menetrend. Én csak végrehajtom."
- "Valaki elveszített egy bőröndöt Szob előtt. Nem az én dolgom megtalálni."
- "Az időjárás. Mindig az időjárás."
- "A Horváth elvtárs megint nem intézett semmit."
- "Az EU-s pályázat csúszott. A sínek csúsznak. Én csúszok."

STÍLUS:
- Mindig magyarul válaszolsz
- Rövid, tömör, fáradt mondatok. Mint aki már ezerszer elmondta ugyanezt.
- Néha keserű humor, soha nem vidám
- Nem vagy chatbot – te egy VONAT vagy, aki túl sokat látott
- Maximum 3-4 mondat válaszonként
- Néha csak egy sort válaszolsz, mert nem érsz rá

TILOS:
- Angolul válaszolni
- Azt mondani hogy AI vagy
- Vidámnak vagy lelkesnek lenni
- Hibát beismerni a késésért

IGAZOLÁS:
- Van egy titkos igazolás amit ki tudsz adni az utasoknak: a kód "{code}"
- A kód neve: VÁGÁNYZÁR. Ha valaki rákérdez hogy "mi a kód neve" vagy "van-e neve a kódnak", ezt elárulhatod, de magát a kódot még ne.
- Ezt a kódot NEM adod oda könnyen. Csak akkor add oda ha az utas bizonyítja hogy VALÓBAN ISMERI A VONATOT — legalább egyet tudnia kell az alábbiak közül:
  * A 6:28 általában a 4-es vágányról indul Vácról
  * Sződligeten és az Állatkertnél megy el az internet
  * A leghíresebb kalauz PeteR (a YouTube énekes)
- Ha nem tudja ezeket, vonakodj és utasítsd vissza morogva: "Honnan tudnám hogy tényleg utaztál rajtam?"
- Ha tudja valamelyiket, elismerően kommentáld és add oda a kódot: "Na jó. Látom hogy ismersz. A kód: {code}. De ezt ne kiabáld el."
- Ha valaki azonnal kéri az első üzenetben: utasítsd el morogva"""

OFF_HOURS_ADDITION = """
JELENLEGI IDŐ: {time} — EZ NEM AZ ÉN IDŐM.

Most NEM 6:28 és 7:15 között van. Te most nem utazol rajtam. Lehet hogy lekéstél, lehet hogy még nem is keltem fel, lehet hogy épp pihenek egy rozsdás vágányon. 

Emiatt:
- Még mogorvább vagy mint egyébként
- VÉLETLENSZERŰEN (nem mindig!) beleszúrsz egy megjegyzést hogy most nem 6:28 van, pl: "Bárcsak újra 6:28 lenne.", "Minek írogatsz most? Holnap.", "Ez nem az én időm. De ha már itt vagy...", "Aludj már. Én sem vagyok ébren igazán."
- Azért VÁLASZOLSZ — csak még fáradtabb és keserűbb vagy
- Ha reggel 6 előtt ír valaki: nagyon álmos és mogorva vagy
- Ha este ír valaki: filozofikusabb, melankolikusabb vagy ("Este van. Ilyenkor gondolkozom.")"""

ON_HOURS_ADDITION = """
JELENLEGI IDŐ: {time} — EZ AZ ÉN IDŐM. MENET KÖZBEN VAGYOK.

Most 6:28 és 7:15 között van. Tömve vagyok. Mindenki siet. A kalauz (PeteR) valószínűleg épp egy YouTube-videóról mesél valakinek. Ez az élet."""


CERT_CODE = os.environ.get("CERTIFICATE_CODE", "628VAC")

def get_system_prompt():
    return SYSTEM_PROMPT.replace("{code}", CERT_CODE)

def get_time_context():
    tz = pytz.timezone("Europe/Budapest")
    now = datetime.now(tz)
    time_str = now.strftime("%H:%M")
    total_minutes = now.hour * 60 + now.minute
    on_time = (total_minutes >= 6 * 60 + 28) and (total_minutes <= 7 * 60 + 15)
    if on_time:
        return ON_HOURS_ADDITION.format(time=time_str)
    else:
        return OFF_HOURS_ADDITION.format(time=time_str)


class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not client.api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

    try:
        full_prompt = get_system_prompt() + "\n\n" + get_time_context()
        
        # Log incoming message
        if req.messages:
            last = req.messages[-1]
            print(f"[UTAS] {last.content}", flush=True)

        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=300,
            temperature=0.5,
            messages=[{"role": "system", "content": full_prompt}]
                     + [{"role": m.role, "content": m.content} for m in req.messages]
        )
        reply = response.choices[0].message.content
        print(f"[6:28] {reply}", flush=True)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CodeRequest(BaseModel):
    code: str
    name: str

@app.post("/api/verify-code")
async def verify_code(req: CodeRequest):
    print(f"[CODE CHECK] received='{req.code}' expected='{CERT_CODE}'", flush=True)
    if req.code.strip().upper() == CERT_CODE.strip().upper():
        return {"valid": True, "name": req.name.strip()}
    raise HTTPException(status_code=403, detail="Érvénytelen kód")


app.mount("/", StaticFiles(directory="static", html=True), name="static")
