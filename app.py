from flask import Flask, request, render_template, redirect, url_for
import pyodbc
import os
import uuid
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# Load .env file
load_dotenv()

app = Flask(__name__)

# Fetch environment variables
SQL_CONNECTION_STRING = os.getenv('SQL_CONNECTION_STRING')
BLOB_CONNECTION_STRING = os.getenv('BLOB_CONNECTION_STRING')
BLOB_CONTAINER_NAME = os.getenv('BLOB_CONTAINER_NAME')

if not SQL_CONNECTION_STRING or not BLOB_CONNECTION_STRING or not BLOB_CONTAINER_NAME:
    print("Error: One or more environment variables are missing!")
    exit(1)  # Stop execution if .env variables are not loaded

# Initialize BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)

# Database Connection
conn = pyodbc.connect(SQL_CONNECTION_STRING)
cursor = conn.cursor()

@app.route('/')
def list_products():
    cursor.execute("SELECT Id, Name, Description, Price, Category, ImageUrl FROM dbo.Products")
    products = cursor.fetchall()
    return render_template('list_products.html', products=products)

@app.route('/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        category = request.form.get('category')
        image_url = None

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                blob_name = f"{uuid.uuid4()}_{file.filename}"
                blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_name)
                blob_client.upload_blob(file, overwrite=True)
                image_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{blob_name}"

        cursor.execute("INSERT INTO dbo.Products (Name, Description, Price, Category, ImageUrl) VALUES (?, ?, ?, ?, ?)",
                       (name, description, price, category, image_url))
        conn.commit()

        return redirect(url_for('list_products'))
    
    return render_template('add_product.html')

@app.route('/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    # Fetch product details to get the image URL
    cursor.execute("SELECT ImageUrl FROM dbo.Products WHERE Id = ?", (product_id,))
    product = cursor.fetchone()

    if product and product.ImageUrl:
        # Extract blob name from URL
        blob_url = product.ImageUrl
        blob_name = blob_url.split("/")[-1]

        # Delete from Blob Storage
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_name)
        blob_client.delete_blob()

    # Delete from SQL Database
    cursor.execute("DELETE FROM dbo.Products WHERE Id = ?", (product_id,))
    conn.commit()

    return redirect(url_for('list_products'))

if __name__ == '__main__':
    app.run(debug=True)
