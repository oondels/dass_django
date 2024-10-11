import re
from unidecode import unidecode
from sqlalchemy import create_engine, text
import pandas as pd
import psycopg2
import io
import os
from dotenv import load_dotenv
from django.http import JsonResponse


load_dotenv()


def remover_caracteres_especiais(txt):
    """
    Remove caracteres especiais de uma string.

    Substitui os caracteres '/', '\\', '-', '.' por espaços, e remove espaços extras.

    Args:
        txt (str): O texto que será processado.

    Returns:
        str: O texto sem os caracteres especiais ou o valor original se for NaN.
    """
    if pd.isna(txt):
        return txt
    # Substitui \ / - . por ' '
    new_text = re.sub(r"[./\\-]", " ", unidecode(txt))
    # Substitui espaços extras por único espaço ' '
    new_text = re.sub(r"\s+", " ", new_text.strip())
    return new_text


def add_value_fabrica(value):
    if pd.isna(value):
        return value

    freq = unidecode("Frequência")
    costura = unidecode("Costura")
    fabrica = unidecode("Fábrica")

    if not fabrica in value:
        if freq in value:
            index = value.find(freq) + len(freq)
            new_value = value[:index] + " " + "Fabrica" + value[index:]
            return new_value
        elif costura in value:
            index = value.find(costura) + len(costura)
            new_value = value[:index] + " " + "Fabrica" + value[index:]
            return new_value
    return value


def format_list(df):
    # Remover espaços dos nomes das colunas e converter para minúsculas
    df.columns = df.columns.str.replace(" ", "").str.lower()

    # Manter apenas as colunas necessárias
    needed_columns = ["chapa", "nome", "cod_setor", "nome_setor", "gestor", "funcao"]
    df_columns = df.columns
    for column in df_columns:
        if column not in needed_columns:
            df = df.drop(columns=[column])

    # Renomear colunas
    print("Renomeando colunas...")
    df = df.rename(
        columns={"chapa": "matricula", "cod_setor": "setor_folha", "gestor": "gerente"}
    )

    # Adicionar colunas de data e hora como None
    df["data_att"] = None
    df["hora_att"] = None

    # Remover caracteres especiais de todas as colunas
    for column in df.columns:
        df[column] = df[column].apply(
            lambda x: remover_caracteres_especiais(str(x)) if pd.notna(x) else x
        )

    # Adicionar valor "Fabrica" para células vazias na coluna 'nome_setor'
    print("Adicionando 'Fabrica' às células vazias...")
    df["nome_setor"] = df["nome_setor"].apply(lambda x: add_value_fabrica(x))
    return df


def att_database(df, selecao, unidade):
    engine_sest = create_engine(os.getenv("DATABASE_URL_SUL"))
    if selecao == "colaboradores":
        df["unidade_dass"] = unidade.upper()
        conn = psycopg2.connect(
            dbname="sest",
            user="postgres",
            password="gdti5s11se",
            host="10.100.1.43",
            port="5432",
        )
        cursor = conn.cursor()

        try:
            max_id_query = f"SELECT MAX(id) FROM colaborador.colaboradores"
            cursor.execute(max_id_query)
            max_id = cursor.fetchone()[0] or 0  # Se não houver valor, iniciar com 0

            alter_sequence_query = f"ALTER SEQUENCE colaborador.colaboradores_id_seq RESTART WITH {max_id + 1}"
            cursor.execute(alter_sequence_query)
            conn.commit()
            print(f"Sequência ajustada para começar em: {max_id + 1}")

        except Exception as e:
            conn.rollback()
            print("Erro ao ajustar sequência:", e)

        # Salvar DataFrame em CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, header=False, sep=";")
        csv_buffer.seek(0)

        # Usar COPY para inserir em massa
        try:
            cursor.copy_expert(
                f"COPY colaborador.{selecao} FROM STDIN WITH CSV DELIMITER ';'",
                csv_buffer,
            )
            conn.commit()
            print("Dados inseridos com sucesso.")
            return JsonResponse(
                {
                    "success": True,
                    "message": "Lista do REP Atualizada com sucesso!",
                }
            )
        except Exception as e:
            conn.rollback()
            print("Erro ao inserir dados:", e)
            JsonResponse(
                {
                    "success": False,
                    "message": "Erro ao inserir Dados!",
                }
            )
        finally:
            cursor.close()
            conn.close()

    with engine_sest.connect() as conn_sest:
        df.to_sql(
            name=selecao,
            con=conn_sest,
            schema="colaborador",
            if_exists="append",
            index=False,
        )
        print("Dados Inseridos")
        return JsonResponse(
            {
                "success": True,
                "message": "Lista de Funcionários Atualizada com sucesso!",
            }
        )
