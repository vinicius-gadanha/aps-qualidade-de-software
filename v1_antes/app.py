# AgendaLab - Sistema de Reserva de Salas e Laboratorios
# Versao 1.0 (versao inicial, desenvolvida antes da avaliacao de qualidade)
#
# Para executar:  python app.py   e abrir http://127.0.0.1:5000
# Usuario inicial: admin / admin123

import sqlite3
import hashlib
from datetime import datetime
from flask import Flask, render_template, request, redirect, session

app = Flask(__name__)
app.secret_key = "chave-secreta-123"

DB = "agendalab.db"


def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        login TEXT UNIQUE,
        senha TEXT,
        perfil TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS salas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        capacidade INTEGER,
        tipo TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS reservas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sala_id INTEGER,
        usuario_id INTEGER,
        data TEXT,
        hora_inicio TEXT,
        hora_fim TEXT,
        motivo TEXT,
        criado_em TEXT)""")
    cur.execute("SELECT * FROM usuarios WHERE login = 'admin'")
    if cur.fetchone() is None:
        senha = hashlib.md5("admin123".encode()).hexdigest()
        cur.execute("INSERT INTO usuarios (nome, login, senha, perfil) VALUES ('Administrador', 'admin', '" + senha + "', 'admin')")
    con.commit()
    con.close()


@app.route("/")
def index():
    if "usuario_id" in session:
        return redirect("/reservas")
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login = request.form["login"]
        senha = request.form["senha"]
        senha_md5 = hashlib.md5(senha.encode()).hexdigest()
        con = sqlite3.connect(DB)
        cur = con.cursor()
        sql = "SELECT id, nome, perfil FROM usuarios WHERE login = '%s' AND senha = '%s'" % (login, senha_md5)
        cur.execute(sql)
        u = cur.fetchone()
        con.close()
        if u:
            session["usuario_id"] = u[0]
            session["nome"] = u[1]
            session["perfil"] = u[2]
            return redirect("/reservas")
        else:
            return render_template("login.html", erro="Erro!")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form["nome"]
        login = request.form["login"]
        senha = request.form["senha"]
        if nome == "" or login == "" or senha == "":
            return render_template("cadastro.html", erro="Preencha tudo")
        con = sqlite3.connect(DB)
        cur = con.cursor()
        senha_md5 = hashlib.md5(senha.encode()).hexdigest()
        cur.execute("INSERT INTO usuarios (nome, login, senha, perfil) VALUES ('%s', '%s', '%s', 'comum')" % (nome, login, senha_md5))
        con.commit()
        con.close()
        return redirect("/login")
    return render_template("cadastro.html")


@app.route("/salas")
def salas():
    if "usuario_id" not in session:
        return redirect("/login")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT * FROM salas")
    lista = cur.fetchall()
    con.close()
    return render_template("salas.html", salas=lista)


@app.route("/salas/nova", methods=["GET", "POST"])
def nova_sala():
    if "usuario_id" not in session:
        return redirect("/login")
    if request.method == "POST":
        nome = request.form["nome"]
        capacidade = request.form["capacidade"]
        tipo = request.form["tipo"]
        con = sqlite3.connect(DB)
        cur = con.cursor()
        cur.execute("INSERT INTO salas (nome, capacidade, tipo) VALUES ('%s', %s, '%s')" % (nome, capacidade, tipo))
        con.commit()
        con.close()
        return redirect("/salas")
    return render_template("sala_form.html")


@app.route("/reservas")
def reservas():
    if "usuario_id" not in session:
        return redirect("/login")
    data = request.args.get("data", "")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    if data != "":
        cur.execute("SELECT * FROM reservas WHERE data = '%s' ORDER BY data, hora_inicio" % data)
    else:
        cur.execute("SELECT * FROM reservas ORDER BY data, hora_inicio")
    rows = cur.fetchall()
    lista = []
    for r in rows:
        # busca o nome da sala
        cur2 = con.cursor()
        cur2.execute("SELECT nome FROM salas WHERE id = %s" % r[1])
        sala = cur2.fetchone()
        # busca o nome do usuario
        cur3 = con.cursor()
        cur3.execute("SELECT nome FROM usuarios WHERE id = %s" % r[2])
        usuario = cur3.fetchone()
        nome_sala = ""
        if sala:
            nome_sala = sala[0]
        nome_usuario = ""
        if usuario:
            nome_usuario = usuario[0]
        lista.append({"id": r[0], "sala": nome_sala, "usuario": nome_usuario, "usuario_id": r[2],
                      "data": r[3], "hora_inicio": r[4], "hora_fim": r[5], "motivo": r[6]})
    con.close()
    return render_template("reservas.html", reservas=lista, data=data)


@app.route("/reservas/nova", methods=["GET", "POST"])
def nova_reserva():
    if "usuario_id" not in session:
        return redirect("/login")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT * FROM salas")
    salas = cur.fetchall()
    if request.method == "POST":
        sala_id = int(request.form["sala_id"])
        data = request.form["data"]
        hora_inicio = request.form["hora_inicio"]
        hora_fim = request.form["hora_fim"]
        motivo = request.form["motivo"]
        # nao deixa reservar no domingo (laboratorio fechado)
        dia = datetime.strptime(data, "%Y-%m-%d").weekday()
        if dia == 6:
            con.close()
            return render_template("reserva_form.html", salas=salas, erro="Erro!")
        if motivo == "":
            con.close()
            return render_template("reserva_form.html", salas=salas, erro="Erro!")
        cur.execute("INSERT INTO reservas (sala_id, usuario_id, data, hora_inicio, hora_fim, motivo, criado_em) VALUES (%s, %s, '%s', '%s', '%s', '%s', '%s')" % (sala_id, session["usuario_id"], data, hora_inicio, hora_fim, motivo, str(datetime.now())))
        con.commit()
        con.close()
        return redirect("/reservas")
    con.close()
    return render_template("reserva_form.html", salas=salas)


@app.route("/reservas/<int:id>/excluir", methods=["POST"])
def excluir_reserva(id):
    if "usuario_id" not in session:
        return redirect("/login")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("DELETE FROM reservas WHERE id = %s" % id)
    con.commit()
    con.close()
    return redirect("/reservas")


@app.route("/relatorio")
def relatorio():
    if "usuario_id" not in session:
        return redirect("/login")
    if session["perfil"] != "admin":
        return redirect("/reservas")
    mes = request.args.get("mes", "")
    if mes == "":
        mes = datetime.now().strftime("%Y-%m")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT * FROM salas")
    salas = cur.fetchall()
    cur.execute("SELECT * FROM reservas")
    todas = cur.fetchall()
    # calcula os dias de funcionamento do mes (segunda a sabado)
    ano = int(mes.split("-")[0])
    m = int(mes.split("-")[1])
    dias = 0
    for d in range(1, 32):
        try:
            dt = datetime(ano, m, d)
            if dt.weekday() != 6:
                dias = dias + 1
        except:
            pass
    horas_disponiveis = dias * 16
    resultado = []
    for s in salas:
        total = 0
        horas = 0
        for r in todas:
            if r[1] == s[0]:
                if r[3][0:7] == mes:
                    total = total + 1
                    hi = r[4].split(":")
                    hf = r[5].split(":")
                    minutos = (int(hf[0]) * 60 + int(hf[1])) - (int(hi[0]) * 60 + int(hi[1]))
                    if minutos > 0:
                        horas = horas + minutos / 60
        if horas_disponiveis > 0:
            ocupacao = horas / horas_disponiveis * 100
        else:
            ocupacao = 0
        if ocupacao < 30:
            nivel = "Baixa"
        elif ocupacao < 70:
            nivel = "Média"
        else:
            nivel = "Alta"
        resultado.append({"sala": s[1], "total": total, "horas": round(horas, 1),
                          "ocupacao": round(ocupacao, 1), "nivel": nivel})
    con.close()
    return render_template("relatorio.html", resultado=resultado, mes=mes)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
