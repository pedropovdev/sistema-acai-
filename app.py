from flask import Flask, render_template, request, redirect, jsonify, session
import sqlite3

app = Flask(__name__)
app.secret_key = "segredo_super_forte_123"


def conectar_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- LOGIN ---------------- #

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        senha = request.form["senha"]

        conn = conectar_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE username = ? AND senha = ?",
            (username, senha)
        ).fetchone()
        conn.close()

        if user:
            session["usuario"] = user["username"]
            session["tipo"] = user["tipo"]
            return redirect("/")
        else:
            return "Login inválido"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


def gerente_only():
    return "tipo" in session and session["tipo"] == "gerente"


def login_required():
    return "usuario" in session


# ---------------- HOME ---------------- #

@app.route("/")
def index():
    if not login_required():
        return redirect("/login")

    conn = conectar_db()
    produtos = conn.execute("SELECT * FROM produtos").fetchall()
    conn.close()
    return render_template("index.html", produtos=produtos)


# ---------------- PRODUTOS ---------------- #

@app.route("/produto/novo", methods=["POST"])
def novo_produto():
    if not gerente_only():
        return "Acesso negado"

    nome = request.form["nome"]
    categoria = request.form["categoria"].strip().lower()
    preco = request.form["preco"]
    estoque = request.form["estoque"]

    conn = conectar_db()
    conn.execute(
        "INSERT INTO produtos (nome, categoria, preco, estoque) VALUES (?, ?, ?, ?)",
        (nome, categoria, preco, estoque)
    )
    conn.commit()
    conn.close()

    return redirect("/")


@app.route("/produto/<int:id>/excluir", methods=["POST"])
def excluir_produto(id):
    if not gerente_only():
        return "Acesso negado"

    conn = conectar_db()
    conn.execute("DELETE FROM produtos WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect("/")


# ---------------- COMANDAS ---------------- #

@app.route("/comanda/nova", methods=["GET", "POST"])
def nova_comanda():
    if not login_required():
        return redirect("/login")

    if request.method == "POST":
        cliente = request.form["cliente"]

        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO comandas (cliente, status, total) VALUES (?, 'aberta', 0)",
            (cliente,)
        )
        conn.commit()
        comanda_id = cursor.lastrowid
        conn.close()

        return redirect(f"/comanda/{comanda_id}")

    return render_template("nova_comanda.html")


@app.route("/comandas")
def comandas_abertas():
    if not login_required():
        return redirect("/login")

    conn = conectar_db()
    comandas = conn.execute("""
        SELECT * FROM comandas
        WHERE status = 'aberta'
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    return render_template("comandas.html", comandas=comandas)


@app.route("/comanda/<int:id>")
def comanda(id):
    if not login_required():
        return redirect("/login")

    conn = conectar_db()

    comanda = conn.execute(
        "SELECT * FROM comandas WHERE id = ?", (id,)
    ).fetchone()

    produtos = conn.execute(
        "SELECT * FROM produtos ORDER BY categoria"
    ).fetchall()

    itens = conn.execute("""
        SELECT i.id, p.nome, i.quantidade, i.subtotal
        FROM itens_comanda i
        JOIN produtos p ON p.id = i.produto_id
        WHERE i.comanda_id = ?
    """, (id,)).fetchall()

    conn.close()

    return render_template(
        "comanda.html",
        comanda=comanda,
        produtos=produtos,
        itens=itens
    )


@app.route("/comanda/<int:id>/adicionar", methods=["POST"])
def adicionar_item(id):
    if not login_required():
        return redirect("/login")

    produto_id = request.form["produto_id"]
    preco = float(request.form["preco"])

    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO itens_comanda (comanda_id, produto_id, quantidade, subtotal)
        VALUES (?, ?, 1, ?)
    """, (id, produto_id, preco))

    cursor.execute("""
        UPDATE comandas SET total = total + ?
        WHERE id = ?
    """, (preco, id))

    conn.commit()
    conn.close()

    return redirect(f"/comanda/{id}")


@app.route("/comanda/<int:comanda_id>/remover/<int:item_id>", methods=["POST"])
def remover_item(comanda_id, item_id):
    if not login_required():
        return redirect("/login")

    conn = conectar_db()
    cursor = conn.cursor()

    item = cursor.execute(
        "SELECT subtotal FROM itens_comanda WHERE id = ?",
        (item_id,)
    ).fetchone()

    if item:
        subtotal = item["subtotal"]

        cursor.execute(
            "DELETE FROM itens_comanda WHERE id = ?",
            (item_id,)
        )

        cursor.execute(
            "UPDATE comandas SET total = total - ? WHERE id = ?",
            (subtotal, comanda_id)
        )

    conn.commit()
    conn.close()

    return redirect(f"/comanda/{comanda_id}")


@app.route("/comanda/<int:id>/fechar", methods=["POST"])
def fechar_comanda(id):
    if not gerente_only():
        return "Acesso negado"

    conn = conectar_db()
    conn.execute("""
        UPDATE comandas
        SET status = 'fechada'
        WHERE id = ?
    """, (id,))
    conn.commit()
    conn.close()

    return redirect("/")

@app.route("/usuario/novo", methods=["GET", "POST"])
def novo_usuario():
    if not gerente_only():
        return "acesso negado"
    if request.method == "POST":
        username = request.form [ "username"]
        senha = request.form [ "senha"]
        tipo = request.form [ "tipo"]

        conn = conectar_db()

        try:
            conn.execute(
                "INSERT INTO usuarios (username, senha, tipo) VALUES (?, ?, ?)",
                (username, senha, tipo)
            )
            conn.commit()

        except:
            conn.close()
            return "usuário já existe"
        conn.close()
        return redirect("/")
    return render_template("novo_usuario.html")

# ---------------- VENDA DIRETA ---------------- #

@app.route("/venda")
def venda():
    if not login_required():
        return redirect("/login")

    conn = conectar_db()

    produtos = conn.execute(
        "SELECT id, nome, preco FROM produtos ORDER BY categoria"
    ).fetchall()

    conn.close()

    return render_template("venda.html", produtos=produtos)
@app.route("/venda/salvar", methods=["POST"])
def salvar_venda():
    if not login_required():
        return jsonify({"erro": "não autorizado"}), 401

    dados = request.get_json()
    total = dados["total"]
    pagamento = dados["pagamento"]
    itens = dados["itens"]

    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO vendas (total, pagamento) VALUES (?, ?)",
        (total, pagamento)
    )
    venda_id = cursor.lastrowid

    for item in itens:
        cursor.execute(
            "INSERT INTO itens_venda (venda_id, produto_id, preco) VALUES (?, ?, ?)",
            (venda_id, item["id"], item["preco"])
        )

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})







# ---------------- RUN ---------------- #


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
