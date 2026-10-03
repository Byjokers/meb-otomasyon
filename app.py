from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime
import pandas as pd

app = Flask(__name__)
app.secret_key = 'meb_super_gizli_anahtar_2027' 

def veritabani_kurulum():
    conn = sqlite3.connect('meb_otomasyon.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tbl_kullanicilar (
            kullanici_adi VARCHAR(50) PRIMARY KEY,
            sifre VARCHAR(50),
            rol VARCHAR(50)
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM tbl_kullanicilar")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO tbl_kullanicilar (kullanici_adi, sifre, rol) VALUES ('admin', '123456', 'İlçe Şefi')")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tbl_ogrenciler (
            tc_kimlik VARCHAR(11) PRIMARY KEY,
            ad_soyad VARCHAR(100),
            dogum_tarihi DATE,
            medeni_durum BOOLEAN,
            mevcut_okul_id INTEGER,
            sinif_seviyesi INTEGER,
            sinif_tekrar_sayisi INTEGER,
            lgs_puani FLOAT,
            obp_puani FLOAT,
            ozel_durum_kodu VARCHAR(50),
            kayit_alani VARCHAR(50),
            tercih_1 VARCHAR(200),
            tercih_2 VARCHAR(200),
            tercih_3 VARCHAR(200)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tbl_nakil_talepleri (
            talep_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tc_kimlik VARCHAR(11),
            talep_turu VARCHAR(50), 
            islem_durumu VARCHAR(20)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tbl_okullar (
            okul_id INTEGER PRIMARY KEY AUTOINCREMENT,
            okul_adi VARCHAR(200),
            okul_turu VARCHAR(50), 
            kontenjan INTEGER,
            taban_puan FLOAT
        )
    ''')
    conn.commit()
    conn.close()
    
veritabani_kurulum()

def dinamik_egitim_yili_hesapla():
    bugun = datetime.now()
    yil = bugun.year
    ay = bugun.month
    if ay >= 9: baslangic_yili = yil
    else: baslangic_yili = yil - 1
    if baslangic_yili < 2027: baslangic_yili = 2027
    return datetime(baslangic_yili, 9, 1), f"{baslangic_yili}-{baslangic_yili + 1} Eğitim Öğretim Yılı"

@app.route('/')
def ana_panel():
    if not session.get('oturum_acik'): return redirect(url_for('login'))
    referans, egitim_yili_metni = dinamik_egitim_yili_hesapla()
    
    conn = sqlite3.connect('meb_otomasyon.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tbl_nakil_talepleri WHERE talep_turu='Örgün Nakil Talebi' AND islem_durumu='Beklemede'")
    orgun_nakil = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tbl_nakil_talepleri WHERE talep_turu='Açık Lise Geçiş Talebi' AND islem_durumu='Beklemede'")
    acik_lise = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tbl_nakil_talepleri WHERE talep_turu='MESEM Geçiş Talebi' AND islem_durumu='Beklemede'")
    mesem = cursor.fetchone()[0]
    conn.close()
    
    istatistikler = {
        'orgun_nakil': orgun_nakil,
        'acik_lise': acik_lise,
        'mesem': mesem,
        'guncel_donem': egitim_yili_metni
    }
    return render_template('dashboard.html', veriler=istatistikler)

@app.route('/ogrenci_ekle', methods=['GET', 'POST'])
def ogrenci_ekle():
    if not session.get('oturum_acik'): return redirect(url_for('login'))
    if request.method == 'POST':
        tc = request.form.get('tc_kimlik')
        ad = request.form.get('ad_soyad')
        dogum = request.form.get('dogum_tarihi')
        ozel = request.form.get('ozel_durum')
        kayit = request.form.get('kayit_alani')
        talep = request.form.get('talep_turu')
        
        t1 = request.form.get('tercih_1', '').strip()
        t2 = request.form.get('tercih_2', '').strip()
        t3 = request.form.get('tercih_3', '').strip()
        lgs = float(request.form.get('lgs_puani') or 0.0)
        obp = float(request.form.get('obp_puani') or 0.0)
        
        conn = sqlite3.connect('meb_otomasyon.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO tbl_ogrenciler 
            (tc_kimlik, ad_soyad, dogum_tarihi, lgs_puani, obp_puani, ozel_durum_kodu, kayit_alani, tercih_1, tercih_2, tercih_3)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tc, ad, dogum, lgs, obp, ozel, kayit, t1, t2, t3))
        
        if talep and talep != 'Yeni Kayıt':
            cursor.execute("SELECT COUNT(*) FROM tbl_nakil_talepleri WHERE tc_kimlik=? AND talep_turu=? AND islem_durumu='Beklemede'", (tc, talep))
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO tbl_nakil_talepleri (tc_kimlik, talep_turu, islem_durumu) VALUES (?, ?, 'Beklemede')", (tc, talep))
                
        conn.commit()
        conn.close()
        return redirect(url_for('ogrenci_havuzu'))
    return render_template('ogrenci_ekle.html')

@app.route('/excel_yukle', methods=['POST'])
def excel_yukle():
    if not session.get('oturum_acik'): return redirect(url_for('login'))
    if 'excel_dosyasi' not in request.files: return redirect(url_for('ogrenci_ekle'))
        
    file = request.files['excel_dosyasi']
    if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        df = pd.read_excel(file)
        conn = sqlite3.connect('meb_otomasyon.db')
        cursor = conn.cursor()
        
        for index, row in df.iterrows():
            tc = str(row.get('TC Kimlik', '')).strip()
            if tc.endswith('.0'): tc = tc[:-2]
            if not tc or tc == 'nan': continue
            
            ad = str(row.get('Ad Soyad', ''))
            dogum = str(row.get('Doğum Tarihi', ''))[:10] 
            kayit = str(row.get('Kayıt Alanı', 'Diger'))
            talep = str(row.get('Talep Türü', 'Yeni Kayıt')).strip()
            
            t1 = str(row.get('Tercih 1', '')).strip()
            t2 = str(row.get('Tercih 2', '')).strip()
            t3 = str(row.get('Tercih 3', '')).strip()
            if t1 == 'nan': t1 = ''
            if t2 == 'nan': t2 = ''
            if t3 == 'nan': t3 = ''
            
            def lgs_duzelt(deger):
                if pd.isna(deger): return 0.0
                s = str(deger).strip().replace(',', '.')
                try:
                    f = float(s)
                    while f > 500: f = f / 10.0
                    return round(f, 4)
                except: return 0.0

            def obp_duzelt(deger):
                if pd.isna(deger): return 0.0
                s = str(deger).strip().replace(',', '.')
                try:
                    f = float(s)
                    while f > 100: f = f / 10.0
                    return round(f, 4)
                except: return 0.0
            
            lgs = lgs_duzelt(row.get('LGS Puanı', 0.0))
            obp = obp_duzelt(row.get('OBP Puanı', 0.0))
            
            ozel = str(row.get('Özel Durum', 'Yok'))
            if ozel == 'nan': ozel = 'Yok'
            if talep == 'nan' or not talep: talep = 'Yeni Kayıt'
            
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO tbl_ogrenciler 
                    (tc_kimlik, ad_soyad, dogum_tarihi, lgs_puani, obp_puani, ozel_durum_kodu, kayit_alani, tercih_1, tercih_2, tercih_3)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (tc, ad, dogum, lgs, obp, ozel, kayit, t1, t2, t3))
                
                if talep != 'Yeni Kayıt':
                    cursor.execute("SELECT COUNT(*) FROM tbl_nakil_talepleri WHERE tc_kimlik=? AND talep_turu=? AND islem_durumu='Beklemede'", (tc, talep))
                    if cursor.fetchone()[0] == 0:
                        cursor.execute("INSERT INTO tbl_nakil_talepleri (tc_kimlik, talep_turu, islem_durumu) VALUES (?, ?, 'Beklemede')", (tc, talep))
            except: pass 
                
        conn.commit()
        conn.close()
    return redirect(url_for('ogrenci_havuzu'))

@app.route('/ogrenci_sil/<tc_kimlik>')
def ogrenci_sil(tc_kimlik):
    if not session.get('oturum_acik'): return redirect(url_for('login'))
    conn = sqlite3.connect('meb_otomasyon.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tbl_ogrenciler WHERE tc_kimlik=?", (str(tc_kimlik).strip(),))
    cursor.execute("DELETE FROM tbl_nakil_talepleri WHERE tc_kimlik=?", (str(tc_kimlik).strip(),))
    conn.commit()
    conn.close()
    return redirect(url_for('ogrenci_havuzu'))

@app.route('/tum_ogrencileri_sil')
def tum_ogrencileri_sil():
    if not session.get('oturum_acik'): return redirect(url_for('login'))
    conn = sqlite3.connect('meb_otomasyon.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tbl_ogrenciler")
    cursor.execute("DELETE FROM tbl_nakil_talepleri")
    conn.commit()
    conn.close()
    return redirect(url_for('ogrenci_havuzu'))

@app.route('/havuz')
def ogrenci_havuzu():
    conn = sqlite3.connect('meb_otomasyon.db')
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tbl_ogrenciler ORDER BY obp_puani DESC")
    ogrenciler = cursor.fetchall()
    conn.close()
    return render_template('havuz.html', ogrenciler=ogrenciler)

@app.route('/okul_ekle', methods=['GET', 'POST'])
def okul_ekle():
    if not session.get('oturum_acik'): return redirect(url_for('login'))
    if request.method == 'POST':
        adi = request.form.get('okul_adi')
        turu = request.form.get('okul_turu')
        kontenjan = int(request.form.get('kontenjan', 0))
        taban_puan = float(request.form.get('taban_puan', 0))
        
        conn = sqlite3.connect('meb_otomasyon.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO tbl_okullar (okul_adi, okul_turu, kontenjan, taban_puan) VALUES (?, ?, ?, ?)', (adi, turu, kontenjan, taban_puan))
        conn.commit()
        conn.close()
        return redirect(url_for('okullar_listesi'))
    return render_template('okul_ekle.html')

@app.route('/okul_sil/<okul_id>')
def okul_sil(okul_id):
    if not session.get('oturum_acik'): return redirect(url_for('login'))
    conn = sqlite3.connect('meb_otomasyon.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tbl_okullar WHERE okul_id=?", (int(okul_id),))
    conn.commit()
    conn.close()
    return redirect(url_for('okullar_listesi'))

@app.route('/okullar')
def okullar_listesi():
    conn = sqlite3.connect('meb_otomasyon.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tbl_okullar")
    okullar = cursor.fetchall()
    conn.close()
    return render_template('okullar.html', okullar=okullar)

@app.route('/eslestirme')
def eslestirme_motoru():
    if not session.get('oturum_acik'): return redirect(url_for('login'))
    conn = sqlite3.connect('meb_otomasyon.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tbl_okullar")
    okullar_db = cursor.fetchall()
    okullar = {}
    for row in okullar_db:
        okullar[row['okul_adi'].strip()] = {
            'turu': str(row['okul_turu']).lower(),
            'kontenjan': int(row['kontenjan'] or 0),
            'taban': float(row['taban_puan'] or 0.0),
            'yerlesenler': [],
            'orijinal_isim': row['okul_adi']
        }
        
    cursor.execute('''
        SELECT o.* 
        FROM tbl_ogrenciler o
        LEFT JOIN tbl_nakil_talepleri t ON o.tc_kimlik = t.tc_kimlik
        WHERE t.talep_turu IS NULL OR t.talep_turu = 'Örgün Nakil Talebi'
    ''')
    tum_ogrenciler = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('''
        SELECT o.*, t.talep_turu, t.islem_durumu 
        FROM tbl_ogrenciler o
        INNER JOIN tbl_nakil_talepleri t ON o.tc_kimlik = t.tc_kimlik
        WHERE t.talep_turu IN ('Açık Lise Geçiş Talebi', 'MESEM Geçiş Talebi')
    ''')
    ozel_komisyon_ogrencileri = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    yerlesim_sonuclari = {}
    yerlesen_tc = set()
    
    def is_lgs(turu): return any(k in turu for k in ['merkezi', 'lgs', 'sınav', 'sinav'])
    def ozel_mi(durum): durum = str(durum).strip(); return 'Yok' not in durum and durum not in ['None', '']
    def kayit_puani(alan): return 3 if alan == 'Kayit_Alaninda' else 2 if alan == 'Komsu_Kayit_Alani' else 1

    lgs_adaylari = [o for o in tum_ogrenciler if float(o.get('lgs_puani') or 0.0) > 0]
    lgs_adaylari.sort(key=lambda x: (float(x.get('lgs_puani') or 0.0), x.get('dogum_tarihi', '')), reverse=True)
    
    for ogrenci in lgs_adaylari:
        if ogrenci['tc_kimlik'] in yerlesen_tc: continue
        tercihler = [str(ogrenci.get(f'tercih_{i}') or '').strip() for i in range(1, 4)]
        for tercih in tercihler:
            if tercih in okullar and is_lgs(okullar[tercih]['turu']):
                hedef = okullar[tercih]
                is_muaf = ozel_mi(ogrenci.get('ozel_durum_kodu'))
                if len(hedef['yerlesenler']) < hedef['kontenjan']:
                    if is_muaf or float(ogrenci.get('lgs_puani') or 0.0) >= hedef['taban']:
                        hedef['yerlesenler'].append(ogrenci)
                        yerlesen_tc.add(ogrenci['tc_kimlik'])
                        break 

    obp_adaylari = [o for o in tum_ogrenciler if o['tc_kimlik'] not in yerlesen_tc]
    obp_adaylari.sort(key=lambda x: (kayit_puani(x.get('kayit_alani', 'Diger')), float(x.get('obp_puani') or 0.0), x.get('dogum_tarihi', '')), reverse=True)
    
    for ogrenci in obp_adaylari:
        tercihler = [str(ogrenci.get(f'tercih_{i}') or '').strip() for i in range(1, 4)]
        for tercih in tercihler:
            if tercih in okullar and not is_lgs(okullar[tercih]['turu']):
                hedef = okullar[tercih]
                if len(hedef['yerlesenler']) < hedef['kontenjan']:
                    hedef['yerlesenler'].append(ogrenci)
                    yerlesen_tc.add(ogrenci['tc_kimlik'])
                    break

    kalan_adaylar = [o for o in tum_ogrenciler if o['tc_kimlik'] not in yerlesen_tc]
    kalan_adaylar.sort(key=lambda x: (kayit_puani(x.get('kayit_alani', 'Diger')), float(x.get('obp_puani') or 0.0), x.get('dogum_tarihi', '')), reverse=True)
    bos_okullar = [okul for okul in okullar.values() if not is_lgs(okul['turu']) and len(okul['yerlesenler']) < okul['kontenjan']]
    
    def okul_onceligi(okul_adi):
        ad_lower = okul_adi.lower()
        if 'meslek' in ad_lower or 'mesleki' in ad_lower or 'teknik' in ad_lower: return 2
        if 'imam' in ad_lower or 'hatip' in ad_lower: return 2
        return 1

    bos_okullar.sort(key=lambda x: (okul_onceligi(x['orijinal_isim']), x['kontenjan'] - len(x['yerlesenler'])), reverse=True)

    for ogrenci in kalan_adaylar:
        for hedef_okul in bos_okullar:
            if len(hedef_okul['yerlesenler']) < hedef_okul['kontenjan']:
                hedef_okul['yerlesenler'].append(ogrenci)
                yerlesen_tc.add(ogrenci['tc_kimlik'])
                break 

    for ad, okul in okullar.items():
        yerlesim_sonuclari[okul['orijinal_isim']] = {
            'turu': 'LGS' if is_lgs(okul['turu']) else 'OBP',
            'ogrenciler': okul['yerlesenler'],
            'doluluk': f"{len(okul['yerlesenler'])} / {okul['kontenjan']}"
        }
        
    gercekten_acikta_kalanlar = [o for o in tum_ogrenciler if o['tc_kimlik'] not in yerlesen_tc]
    
    return render_template('eslestirme.html', 
                           sonuclar=yerlesim_sonuclari, 
                           aciktakiler=gercekten_acikta_kalanlar, 
                           komisyon_bekleyenler=ozel_komisyon_ogrencileri)

@app.route('/komisyon')
def komisyon_paneli():
    if not session.get('oturum_acik'): return redirect(url_for('login'))
    
    conn = sqlite3.connect('meb_otomasyon.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT o.tc_kimlik, o.ad_soyad, t.talep_id, t.talep_turu, t.islem_durumu 
        FROM tbl_ogrenciler o
        INNER JOIN tbl_nakil_talepleri t ON o.tc_kimlik = t.tc_kimlik
        WHERE t.talep_turu IN ('Açık Lise Geçiş Talebi', 'MESEM Geçiş Talebi')
        ORDER BY t.islem_durumu ASC, o.ad_soyad ASC
    ''')
    talepler = cursor.fetchall()
    conn.close()
    
    return render_template('komisyon.html', talepler=talepler)

@app.route('/talep_guncelle/<int:talep_id>/<durum>')
def talep_guncelle(talep_id, durum):
    if not session.get('oturum_acik'): return redirect(url_for('login'))
    if durum not in ['Onaylandı', 'Reddedildi', 'Beklemede']: return redirect(url_for('komisyon_paneli'))
    
    conn = sqlite3.connect('meb_otomasyon.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE tbl_nakil_talepleri SET islem_durumu=? WHERE talep_id=?", (durum, talep_id))
    conn.commit()
    conn.close()
    
    return redirect(url_for('komisyon_paneli'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        kullanici = request.form.get('kullanici_adi')
        sifre = request.form.get('sifre')
        conn = sqlite3.connect('meb_otomasyon.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tbl_kullanicilar WHERE kullanici_adi=? AND sifre=?", (kullanici, sifre))
        kullanici_verisi = cursor.fetchone()
        conn.close()
        
        if kullanici_verisi:
            session['oturum_acik'] = True
            session['kullanici_rolu'] = kullanici_verisi[2] 
            return redirect(url_for('ana_panel'))
        else:
            return render_template('login.html', hata="Hatalı kullanıcı adı veya şifre!")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear() 
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)