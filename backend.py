from fastapi import FastAPI, HTTPException
import mysql.connector
import openai
import os
from pydantic import BaseModel

app = FastAPI()

# Configuración de conexión a MySQL desde Azure
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "TU_HOST_AZURE.mysql.database.azure.com"),
    "user": os.getenv("MYSQL_USER", "adminmysql@TU_HOST_AZURE"),
    "password": os.getenv("MYSQL_PASSWORD", "TU_CONTRASEÑA_AZURE"),
    "database": os.getenv("MYSQL_DATABASE", "ventas_db"),
}

# Configuración de Azure OpenAI
openai.api_type = "azure"
openai.api_base = os.getenv("AZURE_ENDPOINT", "TU_ENDPOINT_AZURE")
openai.api_version = "2023-06-01-preview"
openai.api_key = os.getenv("AZURE_OPENAI_KEY", "TU_CLAVE_AZURE")
DEPLOYMENT_ID = os.getenv("DEPLOYMENT_ID", "ventas-assistant")

# Modelo para recibir consultas desde el frontend
class QueryRequest(BaseModel):
    customer_id: int
    query: str

# Conectar a la base de datos

def connect_db():
    return mysql.connector.connect(**DB_CONFIG)

# Obtener datos de ventas de un cliente
@app.get("/customer/{customer_id}/sales")
def get_customer_sales(customer_id: int):
    try:
        conn = connect_db()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT SUM(v.monto) AS total_compras
        FROM ventas v
        WHERE v.cliente_id = %s;
        """
        cursor.execute(query, (customer_id,))
        sales = cursor.fetchone()

        return sales if sales else {"total_compras": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Obtener productos comprados por un cliente
@app.get("/customer/{customer_id}/products")
def get_customer_products(customer_id: int):
    try:
        conn = connect_db()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT p.nombre, SUM(v.cantidad) AS cantidad_total
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        WHERE v.cliente_id = %s
        GROUP BY p.nombre
        ORDER BY cantidad_total DESC;
        """
        cursor.execute(query, (customer_id,))
        products = cursor.fetchall()

        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Obtener saldo pendiente del cliente
@app.get("/customer/{customer_id}/debt")
def get_customer_debt(customer_id: int):
    try:
        conn = connect_db()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT saldo_pendiente
        FROM clientes
        WHERE id = %s;
        """
        cursor.execute(query, (customer_id,))
        debt = cursor.fetchone()

        return debt if debt else {"saldo_pendiente": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# Consultar OpenAI para decidir si vender o no
@app.post("/generate-response")
def generate_response(request: QueryRequest):
    try:
        sales_data = get_customer_sales(request.customer_id)
        products_data = get_customer_products(request.customer_id)
        debt_data = get_customer_debt(request.customer_id)
        
        context = f"Datos del cliente: Total Compras: {sales_data}, Productos comprados: {products_data}, Deuda: {debt_data}."

        response = openai.ChatCompletion.create(
            engine=DEPLOYMENT_ID,
            messages=[
                {"role": "system", "content": "Eres un asistente que evalúa si un cliente puede comprar basado en su historial de ventas y deuda."},
                {"role": "user", "content": context + " " + request.query}
            ]
        )
        return {"respuesta": response["choices"][0]["message"]["content"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Ejecutar el servidor con Uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)