CREATE TABLE customers (
    id SERIAL PRIMARY KEY, name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL, city VARCHAR(50),
    country VARCHAR(50) DEFAULT 'Nigeria', created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE products (
    id SERIAL PRIMARY KEY, name VARCHAR(200) NOT NULL,
    category VARCHAR(50), price DECIMAL(10,2) NOT NULL, stock INTEGER DEFAULT 0);
INSERT INTO customers (name,email,city) VALUES
('Alice','alice@co.com','Lagos'),('Bob','bob@co.com','London'),
('Charlie','charlie@co.com','Lagos'),('Diana','diana@co.com','Nairobi');
INSERT INTO products (name,category,price,stock) VALUES
('Laptop Pro','Electronics',1299.99,50),('Wireless Mouse','Electronics',29.99,200),
('Python Book','Books',49.99,100);
