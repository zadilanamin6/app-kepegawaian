from flask import Flask, render_template, request, redirect, send_from_directory,session
import sqlite3
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret123"

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # max 2MB

# koneksi database
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

# buat tabel pertama kali
def init_db():
    conn = get_db()
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pegawai (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT,
            nip TEXT,
            jabatan TEXT
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dokumen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pegawai_id INTEGER,
            nama_file TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT
        )
    """)

    # 🔐 PINDAHKAN KE SINI
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        ("admin",)
    ).fetchone()

    if not user:
        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ("admin", "123")
        )

    conn.commit()
    conn.close()
    
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user"] = user["username"]
            return redirect("/")
        else:
            return "Login gagal"

    return render_template("login.html")

@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()
    if "user" not in session:
       return redirect("/login")
    # ===== SIMPAN DATA =====
    if request.method == "POST":
        nama = request.form["nama"]
        nip = request.form["nip"]
        jabatan = request.form["jabatan"]

        files = request.files.getlist("file")

        cursor = conn.execute(
            "INSERT INTO pegawai (nama, nip, jabatan) VALUES (?, ?, ?)",
            (nama, nip, jabatan)
        )
        pegawai_id = cursor.lastrowid

        for file in files:
            if file and allowed_file(file.filename):
                ext = file.filename.rsplit(".", 1)[1].lower()

                folder_nama = nama.replace(" ", "_")
                folder_path = os.path.join(app.config["UPLOAD_FOLDER"], folder_nama)
                os.makedirs(folder_path, exist_ok=True)

                filename = secure_filename(f"{nip}_{file.filename}")
                file.save(os.path.join(folder_path, filename))

                conn.execute(
                    "INSERT INTO dokumen (pegawai_id, nama_file) VALUES (?, ?)",
                    (pegawai_id, f"{folder_nama}/{filename}")
                )

        conn.commit()

    # ===== SEARCH =====
    keyword = request.args.get("keyword")

    if keyword:
        data = conn.execute("""
            SELECT * FROM pegawai
            WHERE nama LIKE ? OR nip LIKE ? OR jabatan LIKE ?
        """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")).fetchall()
    else:
        data = conn.execute("SELECT * FROM pegawai").fetchall()

    dokumen = conn.execute("SELECT * FROM dokumen").fetchall()

    conn.close()

    return render_template("index.html", data=data, dokumen=dokumen)

@app.route("/hapus/<int:id>")
def hapus(id):
    conn = get_db()

    files = conn.execute(
        "SELECT nama_file FROM dokumen WHERE pegawai_id = ?",
        (id,)
    ).fetchall()

    for f in files:
        path = os.path.join(app.config["UPLOAD_FOLDER"], f["nama_file"])
        if os.path.exists(path):
            os.remove(path)

    conn.execute("DELETE FROM dokumen WHERE pegawai_id = ?", (id,))
    conn.execute("DELETE FROM pegawai WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect("/")

# ✅ EDIT
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    conn = get_db()

    if request.method == "POST":
        nama = request.form["nama"]
        nip = request.form["nip"]
        jabatan = request.form["jabatan"]

        conn.execute("""
            UPDATE pegawai
            SET nama = ?, nip = ?, jabatan = ?
            WHERE id = ?
        """, (nama, nip, jabatan, id))
        conn.commit()
        conn.close()
        return redirect("/")

    data = conn.execute("SELECT * FROM pegawai WHERE id = ?", (id,)).fetchone()
    conn.close()

    return render_template("edit.html", data=data)

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")

@app.errorhandler(413)
def too_large(e):
    return render_template("error.html", pesan="Ukuran file terlalu besar! Maksimal 2 MB."), 413
if __name__ == "__main__":
    init_db()
    app.run(debug=True)