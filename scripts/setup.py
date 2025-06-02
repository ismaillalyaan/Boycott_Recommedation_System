import pandas as pd
import mysql.connector
from mysql.connector import Error
import os

# Configurable data file path
DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "products.csv")

try:
    products_df = pd.read_csv(DATA_PATH)
except FileNotFoundError as e:
    print(f"Error: CSV file not found - {e}. Please ensure '{DATA_PATH}' exists.")
    exit(1)
except pd.errors.EmptyDataError:
    print("Error: products.csv is empty. Please check the contents.")
    exit(1)
except pd.errors.ParserError as e:
    print(f"Error: Unable to parse products.csv - {e}. Check for correct formatting and headers.")
    exit(1)
except Exception as e:
    print(f"Unexpected error loading products.csv: {e}")
    exit(1)

try:
    conn = mysql.connector.connect(
        host="DB_HOST",
        user="DB_USER",
        password="DB_PASS",
        database="DB_NAME"
    )
    cursor = conn.cursor()
except Error as e:
    print(f"Error connecting to MySQL database: {e}. Ensure MySQL is running, 'recsys' database exists, and credentials are correct.")
    exit(1)

try:
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("DROP TABLE IF EXISTS similarities;")
    cursor.execute("DROP TABLE IF EXISTS product_clusters;")
    cursor.execute("DROP TABLE IF EXISTS product_embeddings;")
    cursor.execute("DROP TABLE IF EXISTS products;")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
except Error as e:
    print(f"Error dropping tables: {e}. Check if you have permission to drop tables.")
    conn.close()
    exit(1)

try:
    # Create products table
    cursor.execute("""
        CREATE TABLE products (
            product_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            category VARCHAR(100),
            is_boycotted BOOLEAN NOT NULL,
            country TEXT,
            brand TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_category (category),
            INDEX idx_is_boycotted (is_boycotted)
        );
    """)

    # Create product_embeddings table with cascading foreign key
    cursor.execute("""
        CREATE TABLE product_embeddings (
            product_id INT PRIMARY KEY,
            embedding JSON NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
        );
    """)

    # Create product_clusters table with cascading foreign key
    cursor.execute("""
        CREATE TABLE product_clusters (
            product_id INT PRIMARY KEY,
            cluster_id INT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
        );
    """)

    # Create similarities table with cascading foreign keys and indexes
    cursor.execute("""
        CREATE TABLE similarities (
            sim_id INT AUTO_INCREMENT PRIMARY KEY,
            boycott_id INT NOT NULL,
            alt_id INT NOT NULL,
            cosine_score DOUBLE NOT NULL,
            FOREIGN KEY (boycott_id) REFERENCES products(product_id) ON DELETE CASCADE,
            FOREIGN KEY (alt_id) REFERENCES products(product_id) ON DELETE CASCADE,
            CHECK (boycott_id != alt_id),
            INDEX idx_boycott_id (boycott_id),
            INDEX idx_alt_id (alt_id)
        );
    """)

    # Create trigger to enforce boycott_id and alt_id constraints
    cursor.execute("""
        CREATE TRIGGER check_boycott_status
        BEFORE INSERT ON similarities
        FOR EACH ROW
        BEGIN
            DECLARE boycott_status BOOLEAN;
            DECLARE alt_status BOOLEAN;
            
            SELECT is_boycotted INTO boycott_status
            FROM products
            WHERE product_id = NEW.boycott_id;
            
            SELECT is_boycotted INTO alt_status
            FROM products
            WHERE product_id = NEW.alt_id;
            
            IF boycott_status IS NULL OR alt_status IS NULL THEN
                SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Invalid product_id in boycott_id or alt_id';
            ELSEIF boycott_status = FALSE THEN
                SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'boycott_id must reference a boycotted product';
            ELSEIF alt_status = TRUE THEN
                SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'alt_id must reference a non-boycotted product';
            END IF;
        END;
    """)

except Error as e:
    print(f"Error creating tables or trigger: {e}. Verify database connection and SQL syntax.")
    conn.close()
    exit(1)

try:
    for index, row in products_df.iterrows():
        name = row.get("product_name", "Unknown")
        desc = row.get("description", "")
        category = row.get("category", "")
        is_boycotted = bool(row.get("is_boycotted", False))
        country = row.get("country", "Unknown")
        brand = row.get("brand", "Unknown")

        cursor.execute("""
            INSERT INTO products (name, description, category, is_boycotted, country, brand)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, desc, category, is_boycotted, country, brand))
except KeyError as e:
    print(f"Error: Missing column in DataFrame - {e}. Ensure CSV contains 'product_name', 'description', 'category', 'is_boycotted', 'country', 'brand'.")
    conn.rollback()
    conn.close()
    exit(1)
except ValueError as e:
    print(f"Error: Invalid data type in DataFrame - {e}. Check that 'is_boycotted' is boolean-compatible.")
    conn.rollback()
    conn.close()
    exit(1)
except Error as e:
    print(f"Error inserting data: {e}. Check for special characters or data mismatches.")
    conn.rollback()
    conn.close()
    exit(1)

try:
    conn.commit()
    print(f"Successfully inserted {len(products_df)} products into the database.")
except Error as e:
    print(f"Error committing transaction: {e}. Rolling back changes.")
    conn.rollback()
finally:
    cursor.close()
    conn.close()
