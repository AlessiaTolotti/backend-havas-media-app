import os
import time
import pandas as pd
from flask import Flask, request, render_template, url_for, send_from_directory, redirect
from rapidfuzz import process, fuzz
import re
from flask import session
import secrets
from dotenv import load_dotenv
from unidecode import unidecode
from flask import jsonify
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

app.secret_key = os.getenv('FLASK_SECRET_KEY')

users = {
    'admin': os.getenv('ADMIN_PASSWORD'),
    'federica': os.getenv('FEDERICA_PASSWORD'),
    'margherita': os.getenv('MARGHERITA_PASSWORD'),
    'lorenzo': os.getenv('LORENZO_PASSWORD')
}

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)


def carica_excel_pulito(path, sheet_name=None):
    ext = os.path.splitext(path)[1].lower()
    engine = 'pyxlsb' if ext == '.xlsb' else None

    xl = pd.ExcelFile(path, engine=engine)
    sheet_names = xl.sheet_names
    sheet_name = sheet_name or sheet_names[0]

    df_raw = xl.parse(sheet_name, header=None)

    # Trova la riga che ha più valori non nulli (probabile header)
    header_row_idx = df_raw.apply(lambda r: r.notna().sum(), axis=1).idxmax()

    # Rileggi con la riga header corretta
    df_cleaned = pd.read_excel(path, sheet_name=sheet_name, engine=engine, header=header_row_idx)

    return df_cleaned, sheet_names, sheet_name



@app.route('/', methods=['GET', 'POST'])
def home():
    if 'username' in session:
        return main()
    return render_template('home.html')

def main():
    uploaded_files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith(('.xlsx', '.xlsb'))]

    if request.method == 'POST':
        # Controlla se sono stati caricati nuovi file
        file_lavoro = request.files.get('file_lavoro')
        file_dizionario = request.files.get('file_dizionario')

        if file_lavoro and file_dizionario:
            lavoro_path = os.path.join(UPLOAD_FOLDER, file_lavoro.filename)
            dizionario_path = os.path.join(UPLOAD_FOLDER, file_dizionario.filename)
            file_lavoro.save(lavoro_path)
            file_dizionario.save(dizionario_path)

            df, sheet_names, sheet_name = carica_excel_pulito(lavoro_path)

        
        else:
            # Se non sono stati caricati file nuovi, prendi i dati dal form
            lavoro_path = request.form.get('lavoro_path')
            dizionario_path = request.form.get('dizionario_path')

            if not lavoro_path or not dizionario_path:
                # Prendi da selezione file esistenti se i path mancanti
                lavoro_filename = request.form.get('file_lavoro_esistente')
                dizionario_filename = request.form.get('file_dizionario_esistente')
                lavoro_path = os.path.join(UPLOAD_FOLDER, lavoro_filename)
                dizionario_path = os.path.join(UPLOAD_FOLDER, dizionario_filename)

            df, sheet_names, sheet_name = carica_excel_pulito(lavoro_path, sheet_name=request.form.get('sheet_name'))
            

        df.to_pickle(os.path.join(UPLOAD_FOLDER,"df_lavoro_"+session['username']+".pkl"))
        colonne = df.columns.tolist()
        anteprima = df.head(10).to_html(classes='table', index=False)

        return render_template('index.html', colonne=colonne, scelta=True,
                               lavoro_path=lavoro_path,
                               dizionario_path=dizionario_path,
                               anteprima=anteprima,
                               uploaded_files=uploaded_files,
                               sheet_names=sheet_names,
                               sheet_name=sheet_name)

    
    
    return render_template('index.html', scelta=False, uploaded_files=uploaded_files)


@app.route('/api/download/<filename>')
def download(filename):
    return send_from_directory(PROCESSED_FOLDER, filename, as_attachment=True)

@app.route('/api/upload', methods=['POST'])
def upload():
    file_lavoro = request.files.get('file_lavoro')
    file_dizionario = request.files.get('file_dizionario')
    if not file_lavoro or not file_dizionario:
        return jsonify({"error": "File mancanti"}), 400

    lavoro_path = os.path.join(UPLOAD_FOLDER, file_lavoro.filename)
    dizionario_path = os.path.join(UPLOAD_FOLDER, file_dizionario.filename)

    file_lavoro.save(lavoro_path)
    file_dizionario.save(dizionario_path)

    username = session.get('username', 'default')
    threading.Thread(target=thread_carica_excel, args=(lavoro_path, username)).start()

    return jsonify({"message": "Caricamento in corso", "lavoro_path": lavoro_path, "dizionario_path": dizionario_path})

@app.route('/delete_file/<filename>', methods=['POST'])
def delete_file(filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for('home'))

@app.route('/conferma', methods=['POST'])
def conferma():
    start_time = time.time()
    colonna = request.form['colonna']
    lavoro_path = request.form['lavoro_path']
    dizionario_path = request.form['dizionario_path']

    df_lavoro = pd.read_pickle(os.path.join(UPLOAD_FOLDER,'df_lavoro_'+session['username']+'.pkl'))
    df_dizionario = pd.read_excel(dizionario_path)
    df_dizionario.to_pickle(os.path.join(UPLOAD_FOLDER,'df_dizionario_'+session['username']+'.pkl'))

    from_vals = df_dizionario.iloc[:, 0].astype(str).str.upper()
    to_vals = df_dizionario.iloc[:, 1].astype(str)
    mappa = dict(zip(from_vals, to_vals))  #mappa principale From->To
    # Set di valori TO validi (considerati già corretti, non devono essere suggeriti)
    valori_validi = set(to_vals.str.upper())
    valori = df_lavoro[colonna].astype(str).str.upper()
    unici = set(valori.unique())
    non_trovati = list(unici - mappa.keys() - valori_validi)
    trovati = len(valori) - len(non_trovati)

    def clean(text):
        text=unidecode(text)
        text = re.sub(r"[^\w\s']", " ", text)  # Mantiene solo lettere, numeri, spazi E apostrofi
        text = re.sub(r'\s+', ' ', text)     # Normalizza spazi
        return text.strip().upper()
    
    def clean_match(text):
    # Per il confronto: come clean, ma rimuove apostrofi
        text = unidecode(text)
        text = re.sub(r"[^\w\s]", ' ', text)  # Rimuove tutta la punteggiatura
        text = re.sub(r'\s+', ' ', text)
        return text.strip().upper().replace("'", "")

    # Normalizza tutte le chiavi del dizionario
    mappa_clean = {clean_match(k): v for k, v in mappa.items()}
    reverse_lookup = {clean_match(k): k for k in mappa}

    
    suggerimenti = {}
    for v in non_trovati:
        v_str = str(v)
        v_clean = clean_match(v_str)

        matches = process.extract(v_clean, mappa_clean.keys(), limit=4, scorer=fuzz.token_set_ratio)
        # Set per evitare duplicati sul valore finale   #mod
        seen = set()
        suggerimenti[v_str] = []

        for m in matches:
            valore_finale = mappa_clean[m[0]]
            matched_from = reverse_lookup[m[0]]
            score = int(m[1])

            # mostra solo suggerimenti non gia presenti
            if valore_finale not in seen:
                suggerimenti[v_str].append({
                    "valore": valore_finale,
                    "matched_from": matched_from,
                    "score": score
                })
                seen.add(valore_finale)

    return render_template('conferma.html',
                           suggerimenti=suggerimenti,
                           lavoro_path=lavoro_path,
                           dizionario_path=dizionario_path,
                           colonna=colonna,
                           non_trovati=non_trovati,
                           trovati=trovati,
                           start_time=start_time)

@app.route('/elabora', methods=['POST'])
def elabora():
    start_time = float(request.form['start_time'])
    lavoro_path = request.form['lavoro_path']
    dizionario_path = request.form['dizionario_path']
    colonna = request.form['colonna']
    non_trovati = request.form.getlist('non_trovati')
    trovati = int(request.form.get('trovati', '0'))

    #df_dizionario = pd.read_excel(dizionario_path)
    df_dizionario = pd.read_pickle(os.path.join(UPLOAD_FOLDER,'df_dizionario_'+session['username']+'.pkl'))

    mappa = dict(zip(df_dizionario.iloc[:, 0].astype(str), df_dizionario.iloc[:, 1].astype(str)))

    aggiunte_vocab = 0
    for key in non_trovati:
        scelta = request.form.get(f'opzione_{key}')
        if scelta == 'manuale':
            nuovo = request.form.get(f'manuale_{key}')
            if nuovo:
                mappa[key] = nuovo
                aggiunte_vocab += 1
        elif scelta and scelta.startswith('suggerimento_'):
            index = int(scelta.split('_')[1])
            valore_suggerito = request.form.get(f'suggerimento_valore_{key}_{index}')
            if valore_suggerito:
                mappa[key] = valore_suggerito
                aggiunte_vocab += 1

    #df_lavoro = pd.read_excel(lavoro_path)
    df_lavoro = pd.read_pickle(os.path.join(UPLOAD_FOLDER,'df_lavoro_'+session['username']+'.pkl'))
    valori_originali = df_lavoro[colonna].astype(str)
    #df_lavoro[colonna] = valori_originali.replace(mappa)
    df_lavoro[colonna + '_NEW'] = valori_originali.replace(mappa)  #nuova colonna 
    sostituzioni_eseguite = (valori_originali != df_lavoro[colonna]).sum()

    output_file = os.path.join(PROCESSED_FOLDER, 'file_lavoro_modificato_'+session['username']+'.xlsx')
    dizionario_file = os.path.join(PROCESSED_FOLDER, 'dizionario_aggiornato_'+session['username']+'.xlsx')

    df_lavoro.to_excel(output_file, index=False, engine='openpyxl')
    df_dizionario_nuovo = pd.DataFrame(list(mappa.items()), columns=['from', 'to'])
    df_dizionario_nuovo.to_excel(dizionario_file, index=False)

    tempo_esecuzione = round(time.time() - start_time, 2)

    return render_template('risultato.html',
                           lavoro=output_file,
                           dizionario=dizionario_file,
                           tempo=tempo_esecuzione,
                           non_trovati=non_trovati,
                           trovati=trovati,
                           sostituzioni=sostituzioni_eseguite,
                           aggiunte_vocab=aggiunte_vocab)

@app.route('/processed/<path:filename>')
def serve_processed(filename):
    return send_from_directory(PROCESSED_FOLDER, filename)

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/api/login', methods=['POST'])
def login():
    error = None  # inizializzo la variabile error
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        if user in users and users[user] == pwd:
            session['username'] = user
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Credenziali errate!"}), 401

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
    
