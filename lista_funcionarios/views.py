from lista_funcionarios.functions import format_list, att_database
from django.shortcuts import render, redirect
from django.db import connection
from django.http import JsonResponse, Http404, FileResponse
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
import psycopg2
import hashlib
import json
import pandas as pd
import io
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def download_file(request):
    base_dir = Path(__file__).resolve().parent
    file_path = base_dir / "default_files/lista.rar"

    if os.path.exists(file_path):
        response = FileResponse(open(file_path, "rb"), content_type="application/rar")
        response["Content-Disposition"] = f'attachment; filename="{file_path.name}"'
        return response


# Create your views here.
def home(request):
    return render(request, "home.html")


def lista_funcionarios(request):
    jwt_authenticator = JWTAuthentication()
    actions = {"lista_funcionarios": "lista_funcionario", "lista_rep": "colaboradores"}
    try:
        token = request.COOKIES.get("access_token")
        if not token:
            return redirect("/lista_funcionarios/login")

        validated_token = jwt_authenticator.get_validated_token(token)

        if request.method == "POST":
            uploaded_file = request.FILES.get("csv-file")
            data_json = request.headers.get("X-Additional-Data")

            if not uploaded_file:
                print("Sem arquivo")
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Nenhum Arquivo Enviado.",
                    }
                )

            if not data_json:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Selecione a unidade e ação desejada.",
                    }
                )

            data = json.loads(data_json)
            unidade = data.get("unidadeDass")
            acao = data.get("acao")

            if not unidade:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Selecione uma Unidade Dass.",
                    }
                )
            if not acao:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Selecione a Ação Desejada.",
                    }
                )

            try:
                uploaded_file.seek(0)
                selecao = actions[acao]
                # Recria a tabela lista de funcionários
                if acao == "lista_funcionarios":
                    selecao += f"_{unidade.lower()}"
                    lista_funcionario = f"lista_funcionario_{unidade.lower()}"

                    print(f"Atualizando lista de funcionários: {selecao}")
                    try:
                        con = psycopg2.connect(
                            host=os.getenv("HOST_SUL"),
                            database=os.getenv("DATABASE"),
                            user=os.getenv("USER"),
                            password=os.getenv("PASS"),
                            port=os.getenv("PORT"),
                        )
                        con.autocommit = True

                        cur = con.cursor()
                        drop_table = f"DROP TABLE IF EXISTS colaborador.{selecao}"
                        create_table = f"""
                            CREATE TABLE colaborador.{lista_funcionario} (
                                matricula int8 NOT NULL,
                                nome varchar(200) NOT NULL,
                                setor_folha varchar(100) NULL,
                                nome_setor varchar(200) NULL,
                                gerente varchar(200) NOT NULL,
                                funcao varchar(200) NULL,
                                data_att date NULL,
                                hora_att timetz NULL,
                                CONSTRAINT lista_funcionario_pkey_{unidade.lower()} PRIMARY KEY (matricula)
                            );
                            """

                        cur.execute(drop_table)
                        cur.execute(create_table)
                        cur.close()
                        con.close()

                        # Formata lista e atualiza banco de dados
                        df = pd.read_excel(uploaded_file)
                        df = format_list(df)

                        # df.to_excel("./lista_buffered.xlsx", index=False)
                        return att_database(df, selecao, unidade)
                    except Exception as e:
                        print("Falha ao recriar tabela:", e)
                        return JsonResponse(
                            {
                                "success": False,
                                "message": "Erro com a tabelas fornecida. Verifique se o padrão está correto.",
                            }
                        )
                else:
                    df = pd.read_csv(
                        io.StringIO(uploaded_file.read().decode("utf-8")),
                        delimiter=",",
                    )
                    # Verifica se o número de colunas faz sentido, para garantir que o delimitador está correto
                    if len(df.columns) < 4:
                        print("Tentando com ;")
                        uploaded_file.seek(0)

                        df = pd.read_csv(
                            io.StringIO(uploaded_file.read().decode("utf-8")),
                            delimiter=";",
                        )

                    return att_database(df, selecao, unidade)

            except Exception as e:
                print(e)
                return JsonResponse(
                    {
                        "success": False,
                        "message": f"Erro ao processar o arquivo",
                    }
                )

        user_usuario = validated_token.get("user_usuario")
        return render(
            request, "lista_funcionarios.html", {"user_usuario": user_usuario}
        )

    except Exception as e:
        return redirect("/lista_funcionarios/login")


def login(request):

    if request.method == "POST":
        data = json.loads(request.body)

        username = data.get("user")
        password = data.get("password")

        if username and password:
            hashedPassword = hashlib.md5(password.encode("utf-8")).hexdigest()

            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO autenticacao;")
                cursor.execute(
                    """
                    SELECT
                        nome, usuario, funcao, setor, matricula, codigo_barras
                    FROM
                        usuarios
                    WHERE
                        usuario = %s AND
                        senha = %s
                    """,
                    [username.upper(), hashedPassword],
                )
                user = cursor.fetchone()

                if user:

                    user_matricula = user[4]
                    user_usuario = user[1]
                    user_nome = user[0]
                    user_funcao = user[2]
                    user_setor = user[3]

                    refresh = RefreshToken()
                    refresh["user_matricula"] = user_matricula
                    refresh["user_usuario"] = user_usuario
                    refresh["user_nome"] = user_nome
                    refresh["user_funcao"] = user_funcao
                    refresh["user_setor"] = user_setor

                    response = JsonResponse(
                        {
                            "success": True,
                            "redirect_url": "/lista_funcionarios/lista_func",
                            "message": "Login efetuado com sucesso.",
                        }
                    )

                    response.set_cookie(
                        key="access_token",
                        value=str(refresh.access_token),
                        httponly=True,
                        secure=True,
                        samesite="Lax",
                        max_age=1800,
                    )

                    response.set_cookie(
                        key="refresh_token",
                        value=str(refresh),
                        httponly=True,
                        secure=True,
                        samesite="Lax",
                        max_age=86400,
                    )
                    return response
                else:
                    return JsonResponse(
                        {"success": False, "message": "Usuário ou senha inválidos."}
                    )

    return render(request, "login.html")


def logout(request):
    token = request.COOKIES.get("access_token")
    if not token:
        return redirect("/lista_funcionarios")

    response = redirect("/lista_funcionarios")

    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return response
